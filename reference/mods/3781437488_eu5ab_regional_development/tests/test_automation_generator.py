from pathlib import Path
import unittest

from src.eu5autobuild.governor_generator import GOVERNOR_RECOMMENDATION_BUILDINGS
from src.eu5autobuild.rules import load_automation_rules
from tests._generated import _blocks_for_token, generated_fixture
from tests._governor_script_vm import GovernorScriptVM, parse


ROOT = Path(__file__).resolve().parents[1]

class AutomationGeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = generated_fixture()
        cls.catalog = fixture.catalog
        cls.building_count = fixture.building_count
        cls.policy_ids = fixture.policy_ids
        cls.input_source_policy_ids = fixture.input_source_policy_ids
        cls.effects = fixture.effects
        cls.triggers = fixture.triggers
        cls.values = fixture.values
        cls.scripted_guis = fixture.scripted_guis
        cls.engine_queue_gui = fixture.engine_queue_gui
        cls.events = fixture.events
        cls.on_actions = fixture.on_actions
        cls.chinese_localization = fixture.chinese_localization
        cls.english_localization = fixture.english_localization
        cls.construction_demands = fixture.construction_demands

    def test_collector_shortcut_preserves_candidate_classes(self):
        names = (
            "eu5ab_candidate_is_upgrade",
            "eu5ab_candidate_is_expansion",
            "eu5ab_candidate_is_new_build",
            "eu5ab_candidate_has_existing_building",
            "eu5ab_candidate_lacks_existing_building",
        )
        definitions = {
            name: parse(_blocks_for_token(self.triggers, f"\n{name} = ")[0])[0][2]
            for name in names
        }

        class CandidateClassVM(GovernorScriptVM):
            def __init__(self, building, *, existing, replacement):
                super().__init__({"location": {}}, {}, {}, {}, (), (), "location")
                self.building = building
                self.existing = existing
                self.replacement = replacement
                self.scopes["eu5ab_candidate_location"] = "location"

            def test(self, key, operator, value, stack):
                if key == "always":
                    return value == "yes"
                if key == "switch":
                    cases = {k: v for k, _, v in value}
                    return self.condition(cases.get(stack[-1], cases['fallback']), stack)
                if key == "eu5ab_candidate_replaces_existing_building":
                    return self.replacement == (value == "yes")
                if key in definitions:
                    return self.condition(definitions[key], stack) == (value == "yes")
                if key == "this":
                    return stack[-1] == value
                if key == "has_building":
                    return self.existing and value == self.building
                return super().test(key, operator, value, stack)

        known = f"building_type:{next(iter(self.catalog.buildings))}"
        unknown = "building_type:eu5ab_unknown_test_building"
        for building, existing, replacement, expected in (
            (known, True, True, "upgrade"),
            (known, True, False, "expansion"),
            (known, False, False, "new"),
            (unknown, False, False, None),
        ):
            with self.subTest(building=building, existing=existing, replacement=replacement):
                vm = CandidateClassVM(building, existing=existing, replacement=replacement)
                standalone = tuple(
                    kind for kind, trigger in (
                        ("upgrade", "eu5ab_candidate_is_upgrade"),
                        ("expansion", "eu5ab_candidate_is_expansion"),
                        ("new", "eu5ab_candidate_is_new_build"),
                    ) if vm.test(trigger, "=", "yes", [building])
                )
                pooled = next((
                    kind for kind, trigger in (
                        ("upgrade", "eu5ab_candidate_is_upgrade"),
                        ("expansion", "eu5ab_candidate_has_existing_building"),
                        ("new", "eu5ab_candidate_lacks_existing_building"),
                    ) if vm.test(trigger, "=", "yes", [building])
                ), None)
                self.assertEqual(standalone, (expected,) if expected else ())
                self.assertEqual(pooled, expected)

    def test_country_cadence_uses_cheap_first_pass_and_bounded_deep_scoring(self):
        donor = _blocks_for_token(self.effects, '\neu5ab_prepare_production_reference = ')[0]
        self.assertIn('max = 1', donor)
        self.assertIn('has_building_with_at_least_one_level', donor)
        self.assertNotIn("order_by = eu5ab_location_need_score", self.effects)
        self.assertIn("order_by = var:eu5ab_bucket_need_score", self.effects)
        self.assertIn("eu5ab_scan_regional_development_bucket = {", self.effects)
        self.assertIn("eu5ab_finish_regional_development_scan = {", self.effects)
        self.assertEqual(self.effects.count("var:eu5ab_scan_bucket_index = "), 20)
        self.assertGreaterEqual(self.effects.count("max = 30"), 40)
        self.assertNotIn("var:eu5ab_scan_bucket =", self.effects)
        for bucket in range(1, 21):
            bucket_list = f"eu5ab_scan_bucket_{bucket}_locations"
            self.assertIn(f"add_to_variable_list = {{ name = {bucket_list}", self.effects)
            self.assertEqual(self.effects.count(f"variable = {bucket_list}"), 5)
            self.assertEqual(self.effects.count(f"clear_variable_list = {bucket_list}"), 1)
        self.assertIn(
            "eu5ab_scan_attempt_count < { value = var:eu5ab_deep_score_budget }",
            self.effects,
        )
        self.assertNotIn("max = { value = num_locations }", self.effects)
        self.assertIn("eu5ab_diag_covered_locations", self.effects)
        self.assertIn("eu5ab_diag_preliminary_passed", self.effects)
        self.assertIn("eu5ab_wait_months", self.effects)
        self.assertIn("eu5ab_monthly_build_quota", self.effects)
        self.assertIn(
            "eu5ab_constructions_started_this_tick < { value = var:eu5ab_monthly_build_quota }",
            self.effects,
        )
        self.assertIn("eu5ab_location_has_parallel_room = yes", self.effects)
        self.assertIn("eu5ab_build_cooldown value = 3", self.effects)
        self.assertGreaterEqual(self.effects.count("check_range_bounds = no"), 42)

    def test_non_automatic_buildings_are_excluded_from_generated_candidates(self):
        for building_id in GOVERNOR_RECOMMENDATION_BUILDINGS:
            self.assertNotIn(f"this = building_type:{building_id}", self.triggers)
            self.assertNotIn(f"building_type = {building_id}", self.effects)
            self.assertNotIn(f"priority_building_{building_id}", self.scripted_guis)
        self.assertNotIn("settlement_building", self.catalog.buildings)
        self.assertNotIn("building_type:settlement_building", self.effects)
        self.assertNotIn("building_type:settlement_building", self.triggers)

    def test_parallel_worker_is_location_local_and_serial_mode_reuses_it(self):
        worker = _blocks_for_token(
            self.effects, "\neu5ab_run_location_worker = "
        )[0]
        merge = _blocks_for_token(
            self.effects, "\neu5ab_merge_location_worker_results = "
        )[0]
        stage = _blocks_for_token(
            self.effects, "\neu5ab_stage_engine_candidate = "
        )[0]
        scan = _blocks_for_token(
            self.effects, "\neu5ab_scan_regional_development_bucket = "
        )[0]
        capture = _blocks_for_token(
            self.scripted_guis, "\neu5ab_gui_capture_building_capacity = "
        )[0]

        self.assertIn("eu5ab_try_construct_policy_candidate = yes", worker)
        self.assertNotIn("construct_building", worker)
        self.assertNotIn("construct_rgo_upgrade", worker)
        self.assertNotIn("eu5ab_global_budget_remaining", worker)
        self.assertNotIn("eu5ab_q_phase_", worker)
        self.assertIn(
            "set_variable = { name = eu5ab_worker_staged value = 0 }",
            worker,
        )
        for counter in (
            "eu5ab_diag_legal_candidates",
            "eu5ab_diag_fail_workforce",
            "eu5ab_diag_fail_inputs",
            "eu5ab_diag_fail_oversupply",
            "eu5ab_diag_fail_no_legal",
            "eu5ab_diag_rgo_checked",
            "eu5ab_diag_rgo_fail_capacity",
            "eu5ab_diag_rgo_fail_location",
            "eu5ab_diag_rgo_fail_disabled",
            "eu5ab_diag_rgo_fail_finance",
            "eu5ab_diag_rgo_fail_utilization",
            "eu5ab_diag_rgo_fail_market_need",
            "eu5ab_diag_rgo_eligible",
        ):
            initialization = (
                f"set_variable = {{ name = eu5ab_worker_{counter} value = 0 }}"
            )
            self.assertIn(initialization, worker)
            self.assertLess(
                worker.index(initialization),
                worker.index("eu5ab_try_construct_policy_candidate = yes"),
            )
        self.assertIn("has_variable = eu5ab_worker_active", stage)
        for phase in range(1, 9):
            self.assertIn(f"eu5ab_worker_phase_{phase}_types", stage)
            self.assertIn(f"eu5ab_q_phase_{phase}_types", merge)
        self.assertIn(
            "trigger_event_silently = { on_action = eu5ab_parallel_location_scan_on_action }",
            capture,
        )
        self.assertIn("eu5ab_request_building_capacity = yes", scan)
        self.assertIn("else = { eu5ab_run_capacity_worker_once = yes }", capture)

    def test_persistent_scan_registry_is_incremental_and_not_monthly_rebuilt(self):
        register = _blocks_for_token(
            self.effects, "\neu5ab_register_location_for_scan = "
        )[0]
        unregister = _blocks_for_token(
            self.effects, "\neu5ab_unregister_location_from_scan = "
        )[0]
        rebuild = _blocks_for_token(
            self.effects, "\neu5ab_rebuild_scan_registry_v1 = "
        )[0]
        recovery = _blocks_for_token(
            self.effects, "\neu5ab_recover_runtime_after_load = "
        )[0]
        monthly = _blocks_for_token(
            self.effects, "\neu5ab_run_regional_development_policy = "
        )[0]
        finish = _blocks_for_token(
            self.effects, "\neu5ab_finish_regional_development_scan = "
        )[0]

        self.assertIn("eu5ab_scan_bucket_assignment add = 1", register)
        self.assertIn("eu5ab_scan_bucket value = owner.var:eu5ab_scan_bucket_assignment", register)
        self.assertIn("eu5ab_scan_registry_schema_version value = 1", register)
        self.assertIn("every_owned_location = {", rebuild)
        self.assertIn("limit = { has_variable = eu5ab_policy_id }", rebuild)
        self.assertIn("remove_variable = eu5ab_scan_bucket", rebuild)
        self.assertIn("eu5ab_register_location_for_scan = yes", rebuild)
        self.assertIn(
            "NOT = { has_variable = eu5ab_scan_registry_schema_version }",
            recovery,
        )
        self.assertIn("eu5ab_rebuild_scan_registry_v1 = yes", recovery)
        for bucket in range(1, 21):
            name = f"eu5ab_scan_bucket_{bucket}_locations"
            self.assertIn(name, register)
            self.assertIn(name, unregister)
            self.assertIn(f"clear_variable_list = {name}", rebuild)
            self.assertNotIn(f"clear_variable_list = {name}", monthly)
            self.assertNotIn(f"clear_variable_list = {name}", finish)
        self.assertNotIn("every_owned_location = {\n\t\tlimit = { has_variable = eu5ab_policy_id }", monthly)

    def test_load_hook_marks_interruption_before_clearing_and_scheduling(self):
        callback = parse(_blocks_for_token(
            self.on_actions, "\neu5ab_on_cmf_after_load = "
        )[0])[0][2]
        effects = next(body for key, _, body in callback if key == "effect")
        steps = [key for key, _, _ in effects]
        self.assertLess(steps.index("eu5ab_mark_interrupted_scan_on_load"),
                        steps.index("eu5ab_recover_runtime_after_load"))
        self.assertLess(steps.index("eu5ab_recover_runtime_after_load"),
                        steps.index("eu5ab_schedule_scan_resume_after_load"))
        pulse = _blocks_for_token(
            self.on_actions, "\neu5ab_monthly_country_policy_pulse = "
        )[0]
        self.assertIn("NOT = { has_variable = eu5ab_scan_resume_after_load }", pulse)

    def test_performance_settings_are_snapshotted_and_bound_work(self):
        monthly = _blocks_for_token(
            self.effects, "\neu5ab_run_regional_development_policy = "
        )[0]
        scan = _blocks_for_token(
            self.effects, "\neu5ab_scan_regional_development_bucket = "
        )[0]
        for snapshot in (
            "eu5ab_scan_parallel",
            "eu5ab_scan_daily_task_limit",
            "eu5ab_scan_max_additions",
            "eu5ab_scan_early_stop",
        ):
            self.assertIn(snapshot, monthly)
        self.assertIn("eu5ab_scan_daily_task_limit min = 1 max = 30", monthly)
        self.assertIn("eu5ab_scan_max_additions min = 0 max = 600", monthly)
        self.assertIn("eu5ab_update_scan_candidate_target = yes", monthly)
        self.assertIn("eu5ab_scan_reserve_count < { value = var:eu5ab_scan_candidate_target }", scan)
    def test_active_projects_use_confirmed_location_index_and_old_saves_rebuild_it(self):
        monthly = _blocks_for_token(
            self.effects, "\neu5ab_run_regional_development_policy = "
        )[0]
        self.assertIn("variable = eu5ab_active_project_locations", monthly)
        self.assertNotIn(
            "# Count only the exact building types and RGO projects confirmed by this Mod.\n\tevery_owned_location",
            monthly,
        )
        confirm = _blocks_for_token(
            self.effects, "\neu5ab_confirm_engine_candidate = "
        )[0]
        rgo = _blocks_for_token(
            self.effects, "\neu5ab_try_construct_rgo_need = "
        )[0]
        for block in (confirm, rgo):
            self.assertIn("name = eu5ab_active_project_locations", block)
            self.assertEqual(
                block.count(
                    "change_variable = { name = eu5ab_diag_active_mod_projects add = 1 }"
                ),
                1,
            )

        migration = _blocks_for_token(
            self.effects, "\neu5ab_migrate_runtime_v2 = "
        )[0]
        recovery = _blocks_for_token(
            self.effects, "\neu5ab_recover_runtime_after_load = "
        )[0]
        self.assertIn("every_owned_location = {", migration)
        self.assertNotIn("remove_variable = eu5ab_scan_bucket", migration)
        self.assertIn("eu5ab_runtime_schema_version value = 2", migration)
        self.assertNotIn("eu5ab_clear_engine_candidate_queue = yes", recovery)
        self.assertNotIn("remove_variable = eu5ab_scan_active", recovery)
        self.assertIn("eu5ab_refresh_build_pending = yes", recovery)
        self.assertNotIn("eu5ab_pl_recover_sampling", recovery)

    def test_location_pre_score_uses_real_people_threshold_and_population_cap(self):
        workforce = _blocks_for_token(
            self.values, "\neu5ab_location_available_workforce_signal = "
        )[0]
        location_score = _blocks_for_token(
            self.values, "\neu5ab_location_need_score = "
        )[0]
        self.assertIn("unemployed_pops_of_pop_type_in_location", workforce)
        self.assertIn("eu5ab_location_available_workforce_signal >= 0.1", location_score)
        self.assertIn("value = population", location_score)
        self.assertIn("max = 60", location_score)
        self.assertNotIn("multiply = 0.0001", location_score)

    def test_native_recipe_capture_uses_current_active_catalog_union(self):
        prepared = _blocks_for_token(
            self.effects, "\neu5ab_prepare_active_recipe_catalog_view = "
        )[0]
        self.assertIn("eu5ab_prepare_current_normal_catalog = yes", prepared)
        self.assertIn("eu5ab_prepare_current_input_catalog = yes", prepared)
        self.assertIn("name = eu5ab_active_recipe_catalog_view", prepared)
        self.assertIn("eu5ab_active_recipe_catalog_ready", prepared)
        self.assertIn("eu5ab_current_policy_auto_builds_input_sources = yes", prepared)
        self.assertIn("eu5ab_global_fill_market_shortages_when_idle > 0", prepared)

        captured = _blocks_for_token(
            self.effects, "\neu5ab_capture_building_capacity = "
        )[0]
        self.assertLess(
            captured.index("eu5ab_clear_building_capacity = yes"),
            captured.index("eu5ab_active_recipe_capture_needed = yes"),
        )
        self.assertIn("else = { eu5ab_clear_native_recipes = yes }", captured)

        native = _blocks_for_token(
            self.effects, "\neu5ab_begin_native_recipe_capture = "
        )[0]
        self.assertIn("eu5ab_active_recipe_catalog_current = yes", native)
        self.assertIn("eu5ab_native_recipe_relevant_to_active_catalog = yes", native)

    def test_all_buildable_iterators_use_an_explicit_candidate_location_scope(self):
        dispatch_adapters = (
            tuple(f"eu5ab_try_construct_{policy_id}" for policy_id in self.policy_ids)
            + tuple(
                f"eu5ab_try_construct_{policy_id}_input_source"
                for policy_id in self.input_source_policy_ids
            )
            + tuple(f"eu5ab_try_construct_template_slot_{slot}" for slot in range(1, 21))
        )
        self.assertEqual(len(dispatch_adapters), 42)
        for function_name in dispatch_adapters:
            with self.subTest(function_name=function_name):
                blocks = _blocks_for_token(self.effects, f"\n{function_name} = ")
                self.assertEqual(len(blocks), 1)
                self.assertRegex(
                    blocks[0],
                    r"eu5ab_try_construct_current_(policy|input_source) = yes",
                )

        collector_specs = (
            (
                "eu5ab_collect_current_candidate_pools",
                "eu5ab_current_building_allowed",
                "eu5ab_current_",
            ),
            (
                "eu5ab_collect_current_input_candidate_pools",
                "eu5ab_current_input_source_building_allowed",
                "eu5ab_current_input_",
            ),
        )
        candidate_classes = (
            ("upgrade", "eu5ab_candidate_is_upgrade"),
            ("expansion", "eu5ab_candidate_has_existing_building"),
            ("new", "eu5ab_candidate_lacks_existing_building"),
        )
        # Each preset/template catalog is compiled once per country/month.
        # Location workers consume the selected short list without another
        # native all-buildable enumeration.
        self.assertEqual(self.effects.count("ordered_buildable_building_type = {"), 42)
        catalog_builders = _blocks_for_token(
            self.effects, "\neu5ab_rebuild_eu5ab_active_"
        )
        self.assertEqual(len(catalog_builders), 42)
        for block in catalog_builders:
            self.assertEqual(block.count("ordered_buildable_building_type = {"), 1)
            self.assertIn(f"max = {self.building_count}", block)
            self.assertIn("eu5ab_candidate_is_latest_unlocked = yes", block)
            self.assertIn("scope:eu5ab_candidate_location.owner = {", block)
        for function_name, allowed_trigger, pool_prefix in collector_specs:
            with self.subTest(collector=function_name):
                block = _blocks_for_token(self.effects, f"\n{function_name} = ")[0]
                saved_candidate = block.index("save_scope_as = eu5ab_candidate_location")
                owner_scope = block.index("owner = {")
                iterator = block.index("variable = eu5ab_active_catalog_view")
                saved_building = block.index("save_scope_as = eu5ab_candidate_building", iterator)
                self.assertLess(saved_candidate, owner_scope)
                self.assertLess(owner_scope, iterator)
                self.assertLess(iterator, saved_building)
                self.assertNotIn("ordered_buildable_building_type = {", block)
                self.assertNotIn("order_by =", block)
                self.assertNotIn(allowed_trigger, block)
                for deferred_side_effect in (
                    "eu5ab_had_legal_candidate",
                    "eu5ab_failure_cooldown",
                    "eu5ab_candidate_updates_worker_top",
                    "eu5ab_try_construct_saved_building_type",
                ):
                    self.assertNotIn(deferred_side_effect, block)
                for common_trigger in (
                    "eu5ab_current_special_building_allowed",
                    "eu5ab_candidate_location_eligible",
                ):
                    self.assertEqual(block.count(common_trigger), 1)
                variants = 2 if "_input_" in pool_prefix else 1
                self.assertEqual(block.count("eu5ab_prepare_candidate_workforce = yes"), variants)
                for candidate_class, class_trigger in candidate_classes:
                    pool = f"{pool_prefix}{candidate_class}_candidate_pool"
                    self.assertEqual(block.count(class_trigger), 0 if candidate_class == "new" else variants)
                    self.assertIn(
                        f"add_to_variable_list = {{ name = {pool} "
                        "target = scope:eu5ab_candidate_building }",
                        block,
                    )
                self.assertNotIn("eu5ab_candidate_is_expansion = yes", block)
                self.assertNotIn("eu5ab_candidate_is_new_build = yes", block)

        normal_collector = _blocks_for_token(
            self.effects, "\neu5ab_collect_current_candidate_pools = "
        )[0]
        self.assertNotIn("eu5ab_current_input_source_building_allowed", normal_collector)
        self.assertNotIn("eu5ab_upstream_output_shortage", normal_collector)
        input_collector = _blocks_for_token(
            self.effects, "\neu5ab_collect_current_input_candidate_pools = "
        )[0]
        self.assertIn("eu5ab_upstream_output_shortage_preliminary = yes", input_collector)

        staged_feature_specs = (
            ("eu5ab_stage_current_upgrade_candidates", "eu5ab_current_upgrade_candidate_pool"),
            ("eu5ab_stage_current_expansion_candidates", "eu5ab_current_expansion_candidate_pool"),
            ("eu5ab_stage_current_new_candidates", "eu5ab_current_new_candidate_pool"),
            ("eu5ab_stage_current_input_upgrade_candidates", "eu5ab_current_input_upgrade_candidate_pool"),
            ("eu5ab_stage_current_input_expansion_candidates", "eu5ab_current_input_expansion_candidate_pool"),
            ("eu5ab_stage_current_input_new_candidates", "eu5ab_current_input_new_candidate_pool"),
        )
        self.assertGreaterEqual(self.effects.count("save_scope_as = eu5ab_candidate_location"), 8)
        self.assertGreaterEqual(self.effects.count("save_scope_as = eu5ab_candidate_building"), 8)
        for function_name, pool in staged_feature_specs:
            with self.subTest(function_name=function_name):
                block = _blocks_for_token(self.effects, f"\n{function_name} = ")[0]
                saved_candidate = block.index("save_scope_as = eu5ab_candidate_location")
                iterator = block.index("every_in_list = {")
                saved_building = block.index("save_scope_as = eu5ab_candidate_building", iterator)
                self.assertLess(saved_candidate, iterator)
                self.assertLess(iterator, saved_building)
                self.assertEqual(block.count("every_in_list = {"), 1)
                self.assertEqual(block.count(f"variable = {pool}"), 1)
                self.assertNotIn("order_by = eu5ab_candidate_sort_score", block)
                self.assertNotIn("ordered_buildable_building_type = {", block)
                self.assertNotIn("eu5ab_candidate_location_can_build = yes", block)
                for _candidate_class, class_trigger in candidate_classes:
                    self.assertNotIn(class_trigger, block)
                self.assertNotIn("position = 0", block)
                self.assertIn("eu5ab_try_construct_saved_building_type = yes", block)
                self.assertNotIn("location_and_owner_can_build =", block)
                self.assertNotIn("construct_building = {", block)
                self.assertNotIn("building_type = scope:eu5ab_candidate_building", block)
                self.assertNotIn("root = { location_and_owner_can_build", block)
                self.assertNotIn("root.owner", block)
                self.assertNotIn("root.var:eu5ab_candidate_cost", block)
                self.assertNotIn("building_type = prev", block)
                self.assertNotIn("prev.building_base_cost_in_gold", block)

        current_policy = _blocks_for_token(
            self.effects, "\neu5ab_try_construct_current_policy = "
        )[0]
        self.assertLess(
            current_policy.index("eu5ab_collect_current_candidate_pools = yes"),
            current_policy.index("variable = eu5ab_candidate_priority_features"),
        )
        self.assertLess(
            current_policy.index("eu5ab_try_construct_current_input_source = yes"),
            current_policy.index("clear_variable_list = eu5ab_current_upgrade_candidate_pool"),
        )
        input_policy = _blocks_for_token(
            self.effects, "\neu5ab_try_construct_current_input_source = "
        )[0]
        self.assertLess(
            input_policy.index("eu5ab_collect_current_input_candidate_pools = yes"),
            input_policy.index("variable = eu5ab_candidate_priority_features"),
        )
        self.assertLess(
            input_policy.index("variable = eu5ab_candidate_priority_features"),
            input_policy.index("clear_variable_list = eu5ab_current_input_upgrade_candidate_pool"),
        )

        self.assertEqual(self.effects.count("eu5ab_try_construct_saved_building_type = yes"), 6)
        dispatcher_blocks = _blocks_for_token(
            self.effects, "\neu5ab_try_construct_saved_building_type = "
        )
        self.assertEqual(len(dispatcher_blocks), 1)
        dispatcher = dispatcher_blocks[0]
        self.assertIn(
            "scope:eu5ab_candidate_location = { eu5ab_stage_engine_candidate = yes }",
            dispatcher,
        )
        self.assertEqual(dispatcher.count("location_and_owner_can_build = {"), 0)
        self.assertNotIn("construct_building = {", dispatcher)
        self.assertNotIn("building_base_cost_in_gold", dispatcher)
        self.assertEqual(dispatcher.count("NOT = { has_variable = eu5ab_action_taken }"), 1)
        self.assertNotIn("building_type = scope:eu5ab_candidate_building", dispatcher)

        can_build_blocks = _blocks_for_token(
            self.triggers, "\neu5ab_candidate_location_can_build = "
        )
        self.assertEqual(len(can_build_blocks), 1)
        can_build = can_build_blocks[0]
        self.assertEqual(
            can_build.count("scope:eu5ab_candidate_location = {"),
            self.building_count,
        )
        self.assertEqual(
            can_build.count("location_and_owner_can_build = {"),
            self.building_count,
        )
        self.assertIn("switch = {\n\t\ttrigger = this", can_build)
        self.assertEqual(
            can_build.count("\n\t\tbuilding_type:"),
            self.building_count,
        )
        self.assertNotIn("this = building_type:", can_build)

    def test_candidate_triggers_and_values_never_read_the_country_root_as_a_location(self):
        self.assertNotIn("root.", self.triggers)
        self.assertNotIn("root.", self.values)
        combined = self.triggers + self.values
        self.assertIn("scope:eu5ab_candidate_location.owner", combined)
        self.assertIn("scope:eu5ab_candidate_location.market", combined)
        self.assertIn(
            "scope:eu5ab_candidate_location.location_unemployed_population_for_building_type(building_type:granary)",
            combined,
        )
        self.assertIn(
            "scope:eu5ab_candidate_location.location_building_level(building_type:granary)",
            combined,
        )
        self.assertNotIn("location_unemployed_population_for_building_type(this)", combined)
        self.assertNotIn("location_building_level(this)", combined)
        self.assertNotIn("(scope:eu5ab_candidate_building)", combined)

    def test_custom_templates_do_not_store_runtime_rules(self):
        for suffix in (
            "min_cash_reserve",
            "price_min",
            "price_max",
            "annual_budget",
            "budget_mode",
            "budget_multiplier",
            "budget_limit",
            "budget_remaining",
            "rgo_priority",
            "rgo_min_utilization",
            "rgo_monthly_limit",
            "job_fill_deadline_months",
            "native_input_priority",
        ):
            self.assertNotIn(f"name = eu5ab_tpl_1_{suffix} value =", self.effects)
        self.assertIn("name = eu5ab_tpl_1_building_priorities", self.effects)
        self.assertNotIn("name = eu5ab_tpl_1_priority_building_", self.effects)

    def test_basic_needs_use_market_signals_without_building_scope_profit(self):
        for token in (
            "is_projected_to_run_out_of_food_stockpile",
            "market_food_percentage",
            "market_monthly_food_balance",
            "goods_supply_in_market(goods:",
            "goods_demand_in_market(goods:",
            "market_price(goods:",
        ):
            self.assertIn(token, self.values)
        self.assertNotIn("building_potential_profit", self.values)
        self.assertEqual(self.values.count("eu5ab_universal_need_score = {"), 1)
        self.assertEqual(
            self.values.count("\tadd = eu5ab_universal_need_score"),
            len(self.policy_ids) + 21,
        )
        self.assertIn("eu5ab_recipe_expected_output_value = {", self.values)
        self.assertIn("eu5ab_recipe_expected_input_cost = {", self.values)
        self.assertIn("eu5ab_recipe_expected_gross_margin = {", self.values)
        self.assertIn("eu5ab_recipe_economic_efficiency_score = {", self.values)

    def test_actual_profit_mode_uses_bounded_shortlist_and_soft_priority(self):
        default_priority = _blocks_for_token(
            self.values, "\neu5ab_default_candidate_configured_priority = "
        )[0]
        configured_priority = _blocks_for_token(
            self.values, "\neu5ab_current_candidate_configured_priority = "
        )[0]
        self.assertIn("this = building_type:granary", default_priority)
        self.assertIn("eu5ab_tpl_1_building_priorities", configured_priority)
        self.assertIn("max = 10", configured_priority)

        ordinary_stage = _blocks_for_token(
            self.effects, "\neu5ab_stage_current_expansion_candidates = "
        )[0]
        self.assertIn("var:eu5ab_global_candidate_ranking_mode = 2", ordinary_stage)
        self.assertIn(
            "max = { value = "
            "owner.var:eu5ab_global_actual_profit_candidates_per_location }",
            ordinary_stage,
        )
        self.assertIn(
            "max = { value = owner.var:eu5ab_global_candidates_per_location }",
            ordinary_stage,
        )
        self.assertEqual(ordinary_stage.count("order_by = eu5ab_candidate_sort_score"), 4)

        rank = _blocks_for_token(
            self.effects, "\neu5ab_record_actual_profit_candidate = "
        )[0]
        self.assertIn("eu5ab_current_candidate_configured_priority", rank)
        self.assertIn("multiply = 0.01", rank)
        self.assertIn("eu5ab_profit_candidate_magnitude_value < 1", rank)
        self.assertIn("add = scope:eu5ab_candidate_location.eu5ab_engine_adjusted_profit", rank)
        self.assertIn("eu5ab_q_profit_best_rank", rank)
        self.assertNotIn("eu5ab_town_rights", rank)
        self.assertNotIn("eu5ab_current_candidate_score", rank)

        prepare = _blocks_for_token(
            self.effects, "\neu5ab_prepare_actual_profit_selection = "
        )[0]
        self.assertIn("order_by = eu5ab_profit_best_rank_value", prepare)
        self.assertIn("name = eu5ab_q_profit_locations", prepare)
        self.assertIn("set_variable = eu5ab_q_profit_selecting", prepare)
        self.assertIn("name = eu5ab_diag_queue_state value = 6", prepare)

        self.assertIn("GetList('eu5ab_q_profit_locations')", self.engine_queue_gui)
        self.assertIn("GetList('eu5ab_q_profit_best_types')", self.engine_queue_gui)
        self.assertIn("eu5ab_gui_queue_try_profit_candidate", self.engine_queue_gui)
        self.assertIn("GetBuildingTypeProfitInLocation", self.engine_queue_gui)
        profit_round_start = self.engine_queue_gui.index(
            "name = eu5ab_q_profit_validate_round"
        )
        profit_round_end = self.engine_queue_gui.index(
            "name = eu5ab_q_profit_validate_check", profit_round_start
        )
        profit_round = self.engine_queue_gui[profit_round_start:profit_round_end]
        self.assertIn(
            "PdxGuiTriggerAllAnimations('eu5ab_q_probe_approved')",
            profit_round,
        )

        final_gate = _blocks_for_token(
            self.scripted_guis, "\neu5ab_gui_queue_try_profit_candidate = "
        )[0]
        for gate in (
            "eu5ab_ensure_validation_economics = yes",
            "eu5ab_engine_candidate_has_actual_budget = yes",
            "eu5ab_engine_candidate_keeps_actual_cash_reserve = yes",
            "eu5ab_ensure_validation_materials = yes",
        ):
            self.assertIn(gate, final_gate)
        self.assertIn("eu5ab_approve_engine_candidate = yes", final_gate)

        sync = _blocks_for_token(
            self.scripted_guis, "\neu5ab_gui_queue_sync_check = "
        )[0]
        self.assertIn("var:eu5ab_global_candidate_ranking_mode = 2", sync)
        self.assertIn("NOT = { has_variable = eu5ab_q_profit_selecting }", sync)
        self.assertIn("eu5ab_prepare_actual_profit_selection = yes", sync)

        rgo_score = _blocks_for_token(
            self.values, "\neu5ab_rgo_candidate_score = "
        )[0]
        self.assertNotIn("candidate_ranking_mode", rgo_score)

    def test_no_market_location_skips_ordinary_candidates_but_keeps_rgo_route(self):
        router = _blocks_for_token(
            self.effects, "\neu5ab_try_construct_policy_candidate = "
        )[0]
        first_policy = router.index(
            f"eu5ab_try_construct_{self.policy_ids[0]} = yes"
        )
        first_policy_limit = router.rfind("\tif = {", 0, first_policy)
        self.assertIn(
            "market ?= { always = yes }",
            router[first_policy_limit:first_policy],
        )
        rgo = router.index("eu5ab_stage_rgo_candidate = yes")
        self.assertGreater(rgo, first_policy)
        self.assertNotIn(
            "market ?= { always = yes }",
            router[router.rfind("\tif = {", 0, rgo):rgo],
        )

    def test_workforce_pause_and_current_labor_factor_use_distinct_paths(self):
        gate = _blocks_for_token(
            self.triggers, "\neu5ab_has_local_workforce = "
        )[0]
        self.assertIn("eu5ab_global_pause_low_workforce <= 0", gate)
        self.assertIn("eu5ab_candidate_projected_workforce_sufficient = yes", gate)
        self.assertNotIn("eu5ab_tpl_1_pause_low_workforce", gate)
        self.assertNotIn("add = eu5ab_labor_risk_penalty", self.values)
        collector = _blocks_for_token(
            self.effects, "\neu5ab_collect_current_candidate_pools = "
        )[0]
        iterator_limit = collector[: collector.index("save_scope_as = eu5ab_candidate_building")]
        self.assertNotIn("eu5ab_has_local_workforce = yes", iterator_limit)
        self.assertIn("eu5ab_prepare_candidate_workforce = yes", collector)
        self.assertIn("has_variable = eu5ab_candidate_workforce_passed", collector)
        self.assertIn("eu5ab_inputs_available = yes", collector)
        self.assertIn("eu5ab_output_not_oversupplied = yes", collector)
        self.assertIn("eu5ab_had_workforce_blocked_candidate", collector)
        input_collector = _blocks_for_token(
            self.effects, "\neu5ab_collect_current_input_candidate_pools = "
        )[0]
        input_iterator_limit = input_collector[
            : input_collector.index("save_scope_as = eu5ab_candidate_building")
        ]
        self.assertNotIn("eu5ab_has_local_workforce = yes", input_iterator_limit)
        self.assertIn("eu5ab_upstream_output_shortage_preliminary = yes", input_iterator_limit)
        self.assertIn("eu5ab_inputs_available = yes", input_collector)
        self.assertIn("eu5ab_had_workforce_blocked_candidate", input_collector)
        fallback = _blocks_for_token(
            self.effects, "\neu5ab_try_construct_current_policy = "
        )[0]
        self.assertNotIn("ordered_buildable_building_type = {", fallback)
        self.assertIn("eu5ab_had_workforce_blocked_candidate", fallback)
        penalty = _blocks_for_token(self.values, "\neu5ab_candidate_current_labor_factor_live = ")[0]
        self.assertIn("eu5ab_global_pause_low_workforce <= 0", penalty)
        self.assertIn("value = 0.4", penalty)
        rgo_gate = _blocks_for_token(self.triggers, "\neu5ab_rgo_workforce_allowed = ")[0]
        self.assertIn("NOT = { eu5ab_rgo_population_mode = yes }", rgo_gate)
        self.assertIn("eu5ab_rgo_projected_workforce_sufficient = yes", rgo_gate)
        rgo_order = _blocks_for_token(self.values, "\neu5ab_rgo_queue_order_score = ")[0]
        self.assertIn("multiply = eu5ab_rgo_current_labor_factor", rgo_order)

    def test_hidden_gui_bridges_actual_engine_values_and_confirms_queue_growth(self):
        for binding in (
            "GetBuildOrExpandBuildingCost",
            "GetBuildingTypeIncomeToOwnerInLocation",
            "GetBuildingTypeProfitInLocation",
            "CanBuildOrExpandBuilding",
            "BuildOrExpandBuildingDefault",
        ):
            self.assertIn(binding, self.engine_queue_gui)
        for state in (
            "eu5ab_q_validate_candidate",
            "eu5ab_q_probe_approved",
            "eu5ab_q_fire_build",
            "eu5ab_q_confirm_build",
        ):
            self.assertIn(state, self.engine_queue_gui)
        for callback in (
            "eu5ab_gui_queue_try_candidate",
            "eu5ab_gui_queue_sync_check",
            "eu5ab_gui_queue_confirm_candidate",
            "eu5ab_gui_queue_confirm_sync",
        ):
            self.assertIn(callback, self.scripted_guis)

        confirm = _blocks_for_token(
            self.effects, "\neu5ab_confirm_engine_candidate = "
        )[0]
        self.assertIn(
            "eu5ab_approved_building_started = yes",
            confirm,
        )
        self.assertIn("eu5ab_commit_engine_candidate_budget = yes", confirm)
        self.assertIn("eu5ab_release_engine_candidate_reservation = yes", confirm)
        self.assertNotIn("construct_building = {", self.effects)

        probe = _blocks_for_token(
            self.scripted_guis, "\neu5ab_gui_queue_probe_approved = "
        )[0]
        self.assertIn(
            "has_variable = eu5ab_q_active eu5ab_queue_calendar_open = yes NOT = { has_variable = eu5ab_scan_resume_after_load } NOT = { has_variable = eu5ab_q_fire }",
            probe,
        )
        self.assertNotIn(
            "has_variable = eu5ab_q_active has_variable = eu5ab_q_fire",
            probe,
        )

    def test_actual_cost_controls_reservations_budget_cash_and_economic_gate(self):
        metric_gate = _blocks_for_token(
            self.triggers, "\neu5ab_engine_candidate_passes_selected_metric = "
        )[0]
        emergency = _blocks_for_token(
            self.triggers, "\neu5ab_engine_candidate_uses_emergency_override = "
        )[0]
        economic = _blocks_for_token(
            self.triggers, "\neu5ab_engine_candidate_economically_sound = "
        )[0]
        self.assertIn("scope:eu5ab_engine_cost > 0", economic)
        self.assertIn("scope:eu5ab_engine_income", metric_gate)
        self.assertIn("scope:eu5ab_candidate_location.eu5ab_engine_adjusted_profit", metric_gate)
        self.assertIn("value = scope:eu5ab_engine_profit", self.values)
        self.assertIn("eu5ab_recipe_expected_output_value <= 0", economic)
        self.assertIn("eu5ab_engine_candidate_passes_selected_metric = yes", economic)
        self.assertIn("eu5ab_engine_candidate_uses_emergency_override = yes", economic)
        for metric in range(1, 5):
            self.assertIn(
                f"var:eu5ab_global_economic_metric = {metric}", metric_gate
            )
        self.assertEqual(metric_gate.count("multiply = 0.05"), 2)
        self.assertEqual(metric_gate.count("divide = 12"), 2)
        self.assertNotIn("eu5ab_universal_need_score", emergency + economic)

        self.assertIn("eu5ab_engine_candidate_has_emergency_demand = yes", emergency)
        emergency = _blocks_for_token(
            self.triggers, "\neu5ab_engine_candidate_has_emergency_demand = "
        )[0]

        for setting in (
            "emergency_food_exhaustion_override",
            "emergency_food_stockpile_override",
            "emergency_construction_goods_override",
            "emergency_wartime_military_override",
            "emergency_strategic_input_override",
        ):
            self.assertIn(f"eu5ab_global_{setting}", emergency)
        self.assertIn("is_projected_to_run_out_of_food_stockpile = yes", emergency)
        self.assertIn("market_food_percentage <= 0.25", emergency)
        self.assertIn("at_war = yes", emergency)
        self.assertIn("multiply = 0.65", emergency)
        self.assertIn("any_location_in_market = {", emergency)
        self.assertIn("any_buildings_in_location = {", emergency)
        self.assertIn("owner = scope:eu5ab_engine_country", emergency)
        self.assertIn("is_opened = yes", emergency)
        self.assertIn("is_lacking_goods = yes", emergency)

        budget = _blocks_for_token(
            self.triggers, "\neu5ab_engine_candidate_has_actual_budget = "
        )[0]
        self.assertIn("value = scope:eu5ab_engine_cost", budget)
        self.assertIn("add = var:eu5ab_q_planned_budget", budget)
        self.assertNotIn("eu5ab_q_planned_builtin_budget", budget)
        self.assertNotIn("eu5ab_q_planned_tpl_1", budget)

        cash = _blocks_for_token(
            self.triggers, "\neu5ab_engine_candidate_keeps_actual_cash_reserve = "
        )[0]
        self.assertIn("add = var:eu5ab_q_planned_spend", cash)
        self.assertIn(
            "add = scope:eu5ab_candidate_location.eu5ab_current_min_cash_reserve",
            cash,
        )

        approve = _blocks_for_token(
            self.effects, "\neu5ab_approve_engine_candidate = "
        )[0]
        self.assertIn("value = scope:eu5ab_engine_cost", approve)
        self.assertIn("eu5ab_reserve_engine_candidate = yes", approve)
        self.assertNotIn("budget_remaining subtract", approve)

        settle = _blocks_for_token(
            self.effects, "\neu5ab_commit_engine_candidate_budget = "
        )[0]
        self.assertIn(
            "name = eu5ab_budget_charge value = scope:eu5ab_candidate_location.var:eu5ab_q_approved_cost",
            settle,
        )
        self.assertIn('eu5ab_charge_annual_budget = yes', settle)

    def test_construction_material_gate_uses_vanilla_mix_and_same_cycle_commitments(self):
        tools = next(
            item
            for item in self.construction_demands["buildings"]
            if item["building_id"] == "tools_workshop"
        )
        self.assertEqual(tools["demand_id"], "workshop_construction")
        self.assertEqual(tools["goods"]["masonry"], 1.0)

        masonry = _blocks_for_token(
            self.values, "\neu5ab_construction_demand_masonry = "
        )[0]
        self.assertIn("this = building_type:tools_workshop", masonry)
        self.assertIn("add = 1", masonry)
        self.assertIn("MARKET_CONSTRUCTION_NEEDS_BLOCK_FACTOR", self.values)
        self.assertIn("eu5ab_q_market_committed_masonry", self.values)

        gate = _blocks_for_token(
            self.triggers, "\neu5ab_engine_construction_materials_available = "
        )[0]
        self.assertIn("eu5ab_market_masonry_projected_construction_overage < 0", gate)
        self.assertIn('"market_price(goods:masonry)"', gate)
        self.assertIn('"default_price(goods:masonry)"', gate)
        self.assertIn("multiply = 1.5", gate)

        reserve = _blocks_for_token(
            self.effects, "\neu5ab_commit_candidate_construction_demand = "
        )[0]
        self.assertIn("eu5ab_q_market_committed_masonry", reserve)
        self.assertIn("change_local_variable", reserve)
        self.assertIn("eu5ab_reset_committed_construction_demand = yes", self.effects)

    def test_queue_watchdog_requires_real_queue_progress(self):
        start = _blocks_for_token(
            self.effects, "\neu5ab_start_engine_candidate_queue = "
        )[0]
        self.assertIn(
            "eu5ab_reset_engine_candidate_watchdog_progress = yes",
            start,
        )
        self.assertIn(
            "trigger_event_silently = { id = eu5ab_queue_watchdog.1 days = 2 }",
            start,
        )

        watchdog_event = _blocks_for_token(
            self.events, "\neu5ab_queue_watchdog.1 = "
        )[0]
        self.assertIn("type = country_event", watchdog_event)
        self.assertIn("has_variable = eu5ab_q_active", watchdog_event)
        self.assertIn(
            "eu5ab_check_engine_candidate_queue_watchdog = yes",
            watchdog_event,
        )
        self.assertIn(
            "trigger_event_silently = { id = eu5ab_queue_watchdog.1 days = 2 }",
            watchdog_event,
        )

        watchdog = _blocks_for_token(
            self.effects, "\neu5ab_check_engine_candidate_queue_watchdog = "
        )[0]
        for progress in ("phase", "processed", "seen", "confirmed"):
            self.assertIn(
                f"var:eu5ab_q_{progress} > "
                f"{{ value = var:eu5ab_q_watchdog_last_{progress} }}",
                watchdog,
            )
        self.assertIn("eu5ab_q_watchdog_stall_checks >= 2", watchdog)
        self.assertIn("name = eu5ab_diag_queue_state value = 5", watchdog)
        self.assertIn("eu5ab_finish_engine_candidate_queue = yes", watchdog)
        self.assertNotIn("heartbeat", watchdog)
        self.assertNotIn("watchdog", self.scripted_guis)

        snapshot = _blocks_for_token(
            self.effects,
            "\neu5ab_reset_engine_candidate_watchdog_progress = ",
        )[0]
        for progress in ("phase", "processed", "seen", "confirmed"):
            self.assertIn(
                f"name = eu5ab_q_watchdog_last_{progress} "
                f"value = var:eu5ab_q_{progress}",
                snapshot,
            )
        self.assertIn(
            "name = eu5ab_q_watchdog_stall_checks value = 0",
            snapshot,
        )

        phase_reset = _blocks_for_token(
            self.effects, "\neu5ab_reset_engine_priority_phase_progress = "
        )[0]
        profit_selection = _blocks_for_token(
            self.effects, "\neu5ab_prepare_actual_profit_selection = "
        )[0]
        for structural_reset in (phase_reset, profit_selection):
            self.assertIn(
                "eu5ab_reset_engine_candidate_watchdog_progress = yes",
                structural_reset,
            )

        clear = _blocks_for_token(
            self.effects, "\neu5ab_clear_engine_candidate_queue = "
        )[0]
        for variable in (
            "eu5ab_q_watchdog_last_phase",
            "eu5ab_q_watchdog_last_processed",
            "eu5ab_q_watchdog_last_seen",
            "eu5ab_q_watchdog_last_confirmed",
            "eu5ab_q_watchdog_stall_checks",
        ):
            self.assertIn(f"remove_variable = {variable}", clear)

    def test_monthly_check_preserves_last_completed_additions_until_queue_finishes(self):
        monthly = _blocks_for_token(
            self.effects, "\neu5ab_run_regional_development_policy = "
        )[0]
        self.assertNotIn("name = eu5ab_diag_quota_used", monthly)
        self.assertNotIn("name = eu5ab_diag_previous_month_added", monthly)

        finish_queue = _blocks_for_token(
            self.effects, "\neu5ab_finish_engine_candidate_queue = "
        )[0]
        for snapshot in (
            "set_variable = { name = eu5ab_diag_previous_month_added value = var:eu5ab_constructions_started_this_tick }",
        ):
            self.assertIn(snapshot, finish_queue)
        self.assertIn("remove_variable = eu5ab_diag_queue_state", monthly)
        self.assertLess(
            monthly.index("eu5ab_prepare_engine_candidate_queue = yes"),
            monthly.index("remove_variable = eu5ab_diag_queue_state"),
        )

    def test_candidate_feature_order_uses_eight_exact_rank_phases(self):
        current_phase = _blocks_for_token(
            self.triggers,
            "\neu5ab_engine_candidate_in_current_priority_phase = ",
        )[0]
        rgo_phase = _blocks_for_token(
            self.triggers,
            "\neu5ab_rgo_in_current_priority_phase = ",
        )[0]

        for rank in range(1, 5):
            feature_rank = _blocks_for_token(
                self.triggers,
                f"\neu5ab_engine_candidate_feature_rank_{rank} = ",
            )[0]
            for classifier in (
                "eu5ab_candidate_is_upgrade",
                "eu5ab_candidate_is_new_build",
                "eu5ab_candidate_is_expansion",
            ):
                self.assertIn(f"{classifier} = yes", feature_rank)
            for feature in ("upgrade", "new", "expand"):
                self.assertIn(
                    f"eu5ab_candidate_priority_{feature} = {rank}",
                    feature_rank,
                )

            self.assertIn(
                f"eu5ab_q_phase = {rank} "
                "eu5ab_engine_candidate_is_food_emergency = yes "
                f"eu5ab_engine_candidate_feature_rank_{rank} = yes",
                current_phase,
            )
            self.assertIn(
                f"eu5ab_q_phase = {rank + 4} "
                "NOT = { eu5ab_engine_candidate_is_food_emergency = yes } "
                f"eu5ab_engine_candidate_feature_rank_{rank} = yes",
                current_phase,
            )
            self.assertIn(
                f"owner.var:eu5ab_q_phase = {rank} "
                f"owner.var:eu5ab_candidate_priority_rgo = {rank} "
                "eu5ab_rgo_food_emergency_enabled = yes",
                rgo_phase,
            )
            self.assertIn(
                f"owner.var:eu5ab_q_phase = {rank + 4} "
                f"owner.var:eu5ab_candidate_priority_rgo = {rank} "
                "NOT = { eu5ab_rgo_food_emergency_enabled = yes }",
                rgo_phase,
            )

        advance = _blocks_for_token(
            self.effects, "\neu5ab_advance_engine_priority_phase = "
        )[0]
        self.assertIn("var:eu5ab_q_phase < 16", advance)

    def test_two_food_switches_feed_one_hard_emergency_layer(self):
        food_emergency = _blocks_for_token(
            self.triggers, "\neu5ab_food_emergency_enabled = "
        )[0]
        self.assertEqual(
            self.triggers.count("\neu5ab_food_emergency_enabled = {"), 1
        )
        self.assertEqual(
            food_emergency.count("eu5ab_global_emergency_food_exhaustion_override"),
            1,
        )
        self.assertEqual(
            food_emergency.count("eu5ab_global_emergency_food_stockpile_override"),
            1,
        )
        self.assertIn("is_projected_to_run_out_of_food_stockpile = yes", food_emergency)
        self.assertIn("market_food_percentage <= 0.25", food_emergency)

        ordinary_food = _blocks_for_token(
            self.triggers, "\neu5ab_engine_candidate_is_food_emergency = "
        )[0]
        rgo_food = _blocks_for_token(
            self.triggers, "\neu5ab_rgo_food_emergency_enabled = "
        )[0]
        self.assertIn("eu5ab_food_emergency_enabled = yes", ordinary_food)
        self.assertIn("eu5ab_candidate_produces_food = yes", ordinary_food)
        self.assertIn("eu5ab_food_emergency_enabled = yes", rgo_food)
        self.assertIn("raw_material = goods:", rgo_food)

    def test_only_latest_unlocked_replacement_is_scored_and_upgrades_are_preferred(self):
        latest = _blocks_for_token(
            self.triggers, "\neu5ab_candidate_is_latest_unlocked = "
        )[0]
        self.assertIn("switch = {\n\t\ttrigger = this", latest)
        self.assertIn("building_type:tools_guild = {", latest)
        self.assertNotIn("this = building_type:", latest)
        self.assertIn("can_build_building = building_type:tools_workshop", latest)
        self.assertIn("can_build_building = building_type:iron_foundry", latest)

        upgrade = _blocks_for_token(
            self.triggers, "\neu5ab_candidate_replaces_existing_building_worker_live = "
        )[0]
        # Inspect the underlying predicate; the public entry can use worker caches.
        self.assertIn("building_type:paper_mill = {", upgrade)
        self.assertIn("building_type = building_type:paper_manufactory", upgrade)
        self.assertIn("building_type = building_type:paper_workshop", upgrade)
        self.assertIn("building_can_be_upgraded_by =", upgrade)

        self.assertIn(
            "limit = { eu5ab_candidate_replaces_existing_building = yes }",
            self.values,
        )
        self.assertIn(
            f"add = {load_automation_rules(ROOT / 'policies' / 'automation_rules.json').thresholds.upgrade_replacement_bonus}",
            self.values,
        )
        self.assertIn(
            "set_variable = { name = eu5ab_q_approved_build_kind value = 2 }",
            self.effects,
        )
        self.assertIn(
            "set_variable = { name = eu5ab_q_approved_build_kind value = 4 }",
            self.effects,
        )

    def test_shared_runtime_toggles_do_not_expand_per_template_slot(self):
        for global_variable in (
            "eu5ab_global_allow_special_buildings",
            "eu5ab_global_pause_low_workforce",
            "eu5ab_global_stop_input_shortage",
        ):
            self.assertIn(global_variable, self.triggers)
        for slot in range(1, 21):
            for suffix in (
                "allow_special_buildings",
                "pause_low_workforce",
                "stop_input_shortage",
            ):
                variable = f"eu5ab_tpl_{slot}_{suffix}"
                self.assertNotIn(variable, self.triggers)

    def test_input_shortage_has_a_real_upstream_recovery_pass(self):
        current_policy = _blocks_for_token(
            self.effects,
            "\neu5ab_try_construct_current_policy = ",
        )[0]
        shared_input_source = _blocks_for_token(
            self.effects,
            "\neu5ab_try_construct_current_input_source = ",
        )[0]
        input_collector = _blocks_for_token(
            self.effects,
            "\neu5ab_collect_current_input_candidate_pools = ",
        )[0]
        self.assertIn("eu5ab_prepare_current_input_catalog = yes", input_collector)
        self.assertIn("variable = eu5ab_active_input_catalog_policy_", input_collector)
        self.assertIn("eu5ab_prepare_candidate_upstream_market_cache = yes", input_collector)
        self.assertIn("eu5ab_upstream_output_shortage_preliminary = yes", input_collector)
        self.assertNotIn(
            "NOT = { has_variable = eu5ab_location_candidate_staged }",
            current_policy,
        )
        self.assertIn("eu5ab_current_policy_auto_builds_input_sources = yes", current_policy)
        self.assertNotIn("eu5ab_had_input_blocked_candidate", current_policy)
        for feature in ("upgrade", "expansion", "new"):
            self.assertIn(
                f"eu5ab_stage_current_input_{feature}_candidates = yes",
                shared_input_source,
            )
            feature_block = _blocks_for_token(
                self.effects,
                f"\neu5ab_stage_current_input_{feature}_candidates = ",
            )[0]
            self.assertIn(
                f"variable = eu5ab_current_input_{feature}_candidate_pool",
                feature_block,
            )
            self.assertNotIn("eu5ab_current_input_source_building_allowed", feature_block)
            self.assertNotIn("eu5ab_upstream_output_shortage", feature_block)
        ordinary_stage = _blocks_for_token(
            self.effects,
            "\neu5ab_stage_current_upgrade_candidates = ",
        )[0]
        self.assertNotIn("eu5ab_had_input_blocked_candidate", ordinary_stage)
        self.assertIn("eu5ab_current_policy_auto_builds_input_sources = yes", self.effects)
        self.assertIn("eu5ab_upstream_output_shortage = {", self.triggers)
        self.assertIn("goods_supply_in_market(goods:iron)", self.triggers)
        self.assertIn("eu5ab_market_price_iron", self.triggers)
        self.assertIn("market_price(goods:iron)", self.effects)
        self.assertIn("add = 3200", self.values)

    def test_candidate_backfill_has_cmm_toggle_and_scan_snapshot(self):
        registration = next(
            block for block in _blocks_for_token(self.on_actions, "cmm_register_bool_setting = ")
            if "setting_id = candidate_backfill_enabled" in block
        )
        self.assertIn("tab_id = performance group_id = advanced", registration)
        self.assertIn("default_value = 0", registration)
        self.assertIn(
            'name = eu5ab_global_candidate_backfill_enabled value = "variable_map(cmm|flag:eu5ab_regional_development__candidate_backfill_enabled)"',
            self.effects,
        )
        self.assertIn("var:eu5ab_global_candidate_backfill_enabled > 0", self.effects)
        self.assertNotIn("eu5ab_experimental_candidate_backfill", self.effects)

    def test_idle_market_shortage_fallback_is_separate_and_disabled_by_default(self):
        registration = next(
            block
            for block in _blocks_for_token(
                self.on_actions,
                "cmm_register_bool_setting = ",
            )
            if "setting_id = fill_market_shortages_when_idle" in block
        )
        self.assertIn("default_value = 0", registration)
        self.assertIn(
            "name = eu5ab_global_fill_market_shortages_when_idle "
            'value = "variable_map(cmm|flag:eu5ab_regional_development__fill_market_shortages_when_idle)"',
            self.effects,
        )

        current_policy = _blocks_for_token(
            self.effects,
            "\neu5ab_try_construct_current_policy = ",
        )[0]
        self.assertIn(
            "owner.var:eu5ab_global_fill_market_shortages_when_idle > 0",
            current_policy,
        )
        self.assertEqual(
            current_policy.count("eu5ab_try_construct_current_input_source = yes"),
            1,
        )

    def test_rgo_is_deferred_to_strict_feature_order_and_has_independent_quota(self):
        router = self.effects.index("eu5ab_try_construct_policy_candidate = {")
        policy_call = self.effects.index(f"eu5ab_try_construct_{self.policy_ids[0]} = yes", router)
        staged_rgo = self.effects.index("eu5ab_stage_rgo_candidate = yes", policy_call)
        self.assertGreater(staged_rgo, policy_call)
        self.assertNotIn("eu5ab_rgo_candidate_score >", self.effects)
        self.assertIn("eu5ab_q_phase value = 1", self.effects)
        self.assertIn("var:eu5ab_q_phase < 16", self.effects)
        self.assertIn("eu5ab_advance_engine_priority_phase = yes", self.scripted_guis)
        self.assertIn("eu5ab_gui_queue_try_rgo = {", self.scripted_guis)
        self.assertIn("eu5ab_q_validate_rgo", self.engine_queue_gui)
        self.assertIn("eu5ab_rgo_in_current_priority_phase = yes", self.effects)
        self.assertIn("eu5ab_rgo_started_this_tick", self.effects)
        self.assertIn("construct_rgo_upgrade = { }", self.effects)
        self.assertIn(
            "limit = { num_civil_constructions > eu5ab_queue_before_attempt_value }",
            self.effects,
        )
        rgo_utilization = _blocks_for_token(
            self.triggers, "\neu5ab_rgo_utilization_allowed = "
        )[0]
        self.assertIn("rgo_workers >= eu5ab_rgo_current_capacity", rgo_utilization)
        self.assertIn("eu5ab_global_allow_rgo", self.triggers)
        stage_rgo = _blocks_for_token(
            self.effects, "\neu5ab_stage_rgo_candidate = "
        )[0]
        for phase in range(1, 9):
            self.assertEqual(
                stage_rgo.count(
                    f"add_to_variable_list = {{ name = eu5ab_q_phase_{phase}_rgo_unsorted_locations"
                ),
                1,
            )
            self.assertEqual(
                self.engine_queue_gui.count(
                    f"GetList('eu5ab_q_phase_{phase}_rgo_locations')"
                ),
                1,
            )
        rgo_order = _blocks_for_token(
            self.values, "\neu5ab_rgo_queue_order_score = "
        )[0]
        self.assertIn("value = eu5ab_rgo_base_score", rgo_order)
        self.assertIn("multiply = eu5ab_rgo_pending_factor", rgo_order)
        sort_rgo = _blocks_for_token(
            self.effects, "\neu5ab_sort_rgo_candidate_queue = "
        )[0]
        self.assertIn("ordered_in_list = {", sort_rgo)
        self.assertIn("order_by = var:eu5ab_cached_rgo_queue_score", sort_rgo)
        for phase in range(1, 9):
            self.assertIn(
                f"variable = eu5ab_q_phase_{phase}_rgo_unsorted_locations",
                sort_rgo,
            )
            self.assertIn(
                f"add_to_variable_list = {{ name = eu5ab_q_phase_{phase}_rgo_locations",
                sort_rgo,
            )
        self.assertIn(
            "set_variable = { name = eu5ab_cached_rgo_queue_score value = eu5ab_rgo_queue_order_score }",
            self.effects,
        )
        rgo_gate = _blocks_for_token(
            self.triggers, "\neu5ab_rgo_expansion_allowed = "
        )[0]
        for gate in (
            "capacity_available",
            "location_available",
            "enabled",
            "finance_available",
            "utilization_allowed",
            "price_allowed",
            "score_allowed",
        ):
            self.assertIn(f"eu5ab_rgo_{gate} = yes", rgo_gate)
        current_capacity = _blocks_for_token(
            self.values, "\neu5ab_rgo_current_capacity = "
        )[0]
        self.assertIn("value = rgo_level", current_capacity)
        self.assertIn("multiply = eu5ab_rgo_jobs_per_expansion", current_capacity)
        utilization_ratio = _blocks_for_token(
            self.values, "\neu5ab_rgo_utilization_ratio = "
        )[0]
        self.assertIn("value = rgo_workers", utilization_ratio)
        self.assertIn("divide = { value = eu5ab_rgo_current_capacity min = 0.001 }", utilization_ratio)
        rgo_score = _blocks_for_token(
            self.values, "\neu5ab_rgo_candidate_score = "
        )[0]
        self.assertIn("value = eu5ab_rgo_utilization_ratio", rgo_score)
        reserve = _blocks_for_token(
            self.values, "\neu5ab_current_min_cash_reserve = "
        )[0]
        self.assertIn("owner.var:eu5ab_global_min_cash_reserve", reserve)
        rgo_cash = _blocks_for_token(
            self.values, "\neu5ab_rgo_cash_required = "
        )[0]
        self.assertIn("add = eu5ab_current_min_cash_reserve", rgo_cash)

    def test_failure_diagnostics_are_cleared_for_each_monthly_check(self):
        monthly = _blocks_for_token(
            self.effects, "\neu5ab_run_regional_development_policy = "
        )[0]
        for key in (
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
            self.assertIn(
                f"set_variable = {{ name = eu5ab_diag_fail_{key} value = 0 }}",
                monthly,
            )


if __name__ == "__main__":
    unittest.main()
