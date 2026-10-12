"""Naval planning and two-type lifecycle tests executing generated effects.

Topology and engine inputs are fixtures. These are not in-game acceptance tests.
"""
from copy import deepcopy
from dataclasses import replace
import random
import unittest

from src.eu5autobuild.governor_generator import render_governor_gui, render_governor_scripted_guis
from src.eu5autobuild.governor_layout_policy import plan_complete_layout
from src.eu5autobuild.governor_planner import NAVAL_PLANNER
from src.eu5autobuild.governor_model import PropagationBudgetExceeded
from src.eu5autobuild.generator import GLOBAL_RULE_DEFAULTS, render_on_actions
from tests._governor_script_vm import GovernorScriptVM, parse
from tests._generated import _blocks_for_token
from tests.test_governor_layout_policy import locations
from tests.test_governor_transport_runtime import TransportScriptVM
from tests.test_governor_layout_liveness import WorkerTimers


class NavalPlannerTests(unittest.TestCase):
    def test_naval_uses_gain_without_capital_bands(self):
        nodes = locations(5)
        nodes[1] = replace(nodes[1], runtime_value=1000)
        nodes[4] = replace(nodes[4], runtime_value=10000)
        graph = {0: {1}, 1: {0, 2}, 2: {1, 3}, 3: {2, 4}, 4: {3}}
        result = plan_complete_layout({1}, {2, 4}, {0: 100, 1: 80}, nodes, graph, {}, capital=0,
                                      planner=NAVAL_PLANNER)
        self.assertEqual(result["steps"][0]["destination_id"], 4)
        self.assertEqual(result["steps"][0]["transport_band"], 0)

    def isolated(self, values, old=(1,), candidates=(2,), sources=None):
        nodes = {n: replace(v, runtime_value=values[n]) for n, v in locations(len(values)).items()}
        vm = GovernorScriptVM(nodes, {}, {}, sources or {0: 100, **{n: 80 for n in old}}, set(), set(), 0)
        vm.naval_old, vm.naval_candidates = set(old), set(candidates)
        vm.vars[vm.ROOT].update(eu5ab_naval_gov_transport_schema=2, eu5ab_naval_gov_transport_road_tier=0)
        return vm

    def fixture(self):
        vm = TransportScriptVM(nodes=range(10), capital=0,
            edges=((0, 1), (2, 3), (3, 4), (4, 5), (6, 7), (7, 8), (8, 9)),
            sources={1: 80, 2: 160, 4: 80, 6: 80, 8: 80})
        vm.connected = {0, 1}
        vm.candidates = set()
        vm.naval_candidates = {3, 5, 7, 9}
        vm.buildings = {(1, "local_governor"): 1, (2, "local_governor"): 1,
                        **{(n, "naval_governor"): 1 for n in (2, 4, 6, 8)}}
        vm.country_modifiers["num_naval_governors"] = 4
        vm.vars[vm.ROOT]["eu5ab_global_naval_governor_migration_threshold_percent"] = 0
        return vm

    def finish_naval(self, vm):
        for _ in range(3000):
            if "eu5ab_naval_planner_scan_active" not in vm.vars[vm.ROOT]:
                return
            vm.call("eu5ab_naval_layout_tick")
        self.fail("Naval job did not terminate")

    def published(self, vm, prefix="eu5ab_layout_"):
        return ({k: v for k, v in vm.vars[vm.ROOT].items()
                 if k.startswith(prefix + "result_") or k.startswith(prefix + "candidate_")},
                {n: {k: v for k, v in values.items() if k.startswith(prefix + "row_")}
                 for n, values in vm.vars.items()})

    def test_generated_naval_matches_reference_on_disconnected_graphs_and_straits(self):
        for seed in range(20):
            with self.subTest(seed=seed):
                rng = random.Random(seed)  # nosec B311: deterministic test fixture, not a secret
                nodes = {n: replace(v, runtime_value=rng.randint(1, 10)*100) for n, v in locations(8).items()}
                edges = [(a, b) for a in range(1, 8) for b in range(a+1, 8) if rng.random() < .4]
                graph = {n: {b if a == n else a for a, b in edges if n in (a, b)} for n in nodes}
                roads = {frozenset(e): "railroad" for e in edges}
                old, candidates, sources = {1, 3, 5}, {2, 4, 6, 7}, {0: 100, 1: 80, 3: 95, 5: 80, 6: 20}
                special = {frozenset(edges[0])} if edges else set()
                vm = GovernorScriptVM(nodes, graph, roads, sources, set(), set(), 0)
                vm.naval_old, vm.naval_candidates, vm.special_edges = old, candidates, special
                vm.vars[vm.ROOT].update(eu5ab_naval_gov_transport_schema=2, eu5ab_naval_gov_transport_road_tier=0)
                vm.call("eu5ab_naval_layout_begin")
                self.finish_naval(vm)
                expected = plan_complete_layout(old, candidates, sources, nodes, graph, roads, capital=0,
                                                 planner=NAVAL_PLANNER, special_edges=special)
                root = vm.vars[vm.ROOT]
                rows = {n: v["eu5ab_naval_layout_row_to"] for n, v in vm.vars.items() if "eu5ab_naval_layout_row_to" in v}
                self.assertEqual(set(rows), old)
                self.assertEqual(set(rows.values()), {r["destination_id"] for r in expected["steps"]})
                self.assertAlmostEqual(root["eu5ab_naval_layout_result_net"], expected["modeled_net"], places=3)
                for rank, candidate in enumerate(expected["top_candidates"], 1):
                    p = f"eu5ab_naval_layout_candidate_{rank}"
                    self.assertEqual(root[p + "_to"], candidate["destination_id"])
                    self.assertAlmostEqual(root[p + "_net"], candidate["net"], places=3)

    def test_manual_completes_both_while_paused_with_auto_off_and_is_repeatable(self):
        vm = self.fixture()
        vm.cmm_settings.update(eu5ab_global_governor_recommendations_enabled=0, eu5ab_global_governor_migration_enabled=0)
        vm.call("eu5ab_governor_manual_recalculation")
        expected = self.published(vm), self.published(vm, "eu5ab_naval_layout_")
        vm.call("eu5ab_governor_manual_recalculation")
        self.assertEqual(expected, (self.published(vm), self.published(vm, "eu5ab_naval_layout_")))
        root = vm.vars[vm.ROOT]
        for prefix in ("eu5ab_governor_", "eu5ab_naval_planner_"):
            self.assertNotIn(prefix + "scan_active", root)
            self.assertNotIn(prefix + "manual_run", root)
        self.assertEqual(root["eu5ab_layout_result_count"], 2)
        self.assertEqual(root["eu5ab_naval_layout_result_count"], 4)
        self.assertEqual(vm.vars[2]["eu5ab_naval_layout_base"], 80)  # Other seat at the same site survives removal.

    def test_fresh_naval_construction_counts_once_and_excludes_target(self):
        vm = self.fixture()
        vm.country_modifiers["num_naval_governors"] = 6
        vm.construction = {(3, "naval_governor"): 1, (2, "naval_governor"): 1}
        vm.call("eu5ab_naval_planner_manual_recalculation")
        root = vm.vars[vm.ROOT]
        self.assertEqual(root["eu5ab_naval_gov_fresh_naval_occupied"], 5)
        self.assertEqual(root["eu5ab_naval_layout_result_count"], 4)
        self.assertNotIn(3, [root.get(f"eu5ab_naval_top_{i}") for i in (1, 2, 3)])
        self.assertNotIn(3, [root.get(f"eu5ab_naval_layout_candidate_{i}_to") for i in (1, 2, 3)])
        vm.country_modifiers["num_naval_governors"] = 5
        vm.call("eu5ab_naval_planner_manual_recalculation")
        self.assertNotIn("eu5ab_naval_top_1", root)
        self.assertEqual(root["eu5ab_naval_gov_sync_status"], 1)

    def test_failure_of_one_type_does_not_erase_the_other(self):
        for kind in ("local", "naval"):
            with self.subTest(kind=kind):
                vm = self.fixture()
                tick = "eu5ab_layout_tick" if kind == "local" else "eu5ab_naval_layout_tick"
                vm.definitions[tick] = []  # Inject a non-progressing worker.
                vm.call("eu5ab_governor_manual_recalculation")
                failed = "eu5ab_layout_" if kind == "local" else "eu5ab_naval_layout_"
                valid = "eu5ab_naval_layout_" if kind == "local" else "eu5ab_layout_"
                self.assertIn(failed + "failed", vm.vars[vm.ROOT])
                self.assertIn(valid + "has_results", vm.vars[vm.ROOT])
                self.assertNotIn("eu5ab_governor_scan_active", vm.vars[vm.ROOT])
                self.assertNotIn("eu5ab_naval_planner_scan_active", vm.vars[vm.ROOT])

    def test_old_callbacks_cannot_republish_replaced_automatic_jobs(self):
        vm = self.fixture()
        vm.call("eu5ab_governor_run_scheduled_planners")
        vm.call("eu5ab_layout_tick")
        vm.call("eu5ab_naval_layout_tick")
        vm.call("eu5ab_governor_manual_recalculation")
        expected = self.published(vm), self.published(vm, "eu5ab_naval_layout_")
        for effect in ("eu5ab_layout_watchdog", "eu5ab_naval_layout_watchdog", "eu5ab_layout_tick", "eu5ab_naval_layout_tick"):
            vm.call(effect)
        self.assertEqual(expected, (self.published(vm), self.published(vm, "eu5ab_naval_layout_")))

    def test_naval_setting_refresh_and_pages_do_not_change_local_state(self):
        vm = self.fixture()
        vm.call("eu5ab_governor_manual_recalculation")
        expected = self.published(vm)
        root = vm.vars[vm.ROOT]
        root.update(eu5ab_local_migration_cooldown=7, eu5ab_layout_confirmation_streak=1,
                    eu5ab_naval_planner_dirty=1, eu5ab_global_naval_governor_migration_threshold_percent=200)
        vm.call("eu5ab_governor_run_scheduled_planners")
        self.finish_naval(vm)
        guis = dict((k, v) for k, _, v in parse(render_governor_scripted_guis()))
        action = next(v for k, _, v in guis["eu5ab_gui_naval_layout_next"] if k == "effect")
        vm.execute(action, [vm.ROOT])
        self.assertEqual(root["eu5ab_naval_layout_page"], 1)
        self.assertEqual(root["eu5ab_layout_page"], 0)
        self.assertEqual(root["eu5ab_local_migration_cooldown"], 7)
        self.assertEqual(root["eu5ab_layout_confirmation_streak"], 1)
        self.assertEqual(expected, self.published(vm))

    def test_old_save_discards_work_but_preserves_zero_setting_mute_and_cooldowns(self):
        vm = self.fixture()
        root = vm.vars[vm.ROOT]
        root.pop("eu5ab_planner_schema")
        root.update(eu5ab_governor_scan_active=1, eu5ab_naval_planner_scan_active=1,
                    eu5ab_global_governor_migration_threshold_percent=0,
                    eu5ab_local_migration_cooldown=7, eu5ab_naval_migration_cooldown=5,
                    cmf_muted_naval_alert=1)
        vm.maps[vm.ROOT]["cmm"] = {"flag:eu5ab_regional_development__governor_migration_threshold_percent": 0}
        settings = deepcopy(vm.maps)
        original_value = vm.value

        def checked_value(value, stack):
            if value == "var:eu5ab_planner_schema":
                self.assertIn("eu5ab_planner_schema", vm.vars[stack[-1]])
            return original_value(value, stack)

        vm.value = checked_value
        vm.call("eu5ab_governor_ensure_planner_schema")
        expected = deepcopy(root)
        vm.call("eu5ab_governor_ensure_planner_schema")
        self.assertEqual(root, expected)
        root.update(eu5ab_planner_schema=1, eu5ab_layout_has_results=1)
        vm.call("eu5ab_governor_ensure_planner_schema")
        self.assertEqual(root, expected)
        self.assertEqual(vm.maps, settings)
        self.assertEqual(root["eu5ab_global_governor_migration_threshold_percent"], 0)
        self.assertEqual(root["cmf_muted_naval_alert"], 1)
        self.assertEqual((root["eu5ab_local_migration_cooldown"], root["eu5ab_naval_migration_cooldown"]), (7, 5))
        self.assertNotIn("eu5ab_governor_scan_active", root)
        self.assertNotIn("eu5ab_naval_planner_scan_active", root)

    def test_monthly_pulse_does_not_initialize_ai_planners(self):
        vm = self.fixture()
        vm.vars[vm.ROOT].pop("eu5ab_planner_schema")
        original_test = vm.test
        vm.test = lambda key, op, value, stack: (
            value == "no" if key == "is_human"
            else original_test(key, op, value, stack)
        )
        expected = deepcopy(vm.vars)
        vm.call("eu5ab_governor_monthly_pulse")
        self.assertEqual(vm.vars, expected)
        self.assertEqual(getattr(vm, "scheduled_events", []), [])

    def test_other_type_source_change_invalidates_a_running_plan(self):
        vm = self.fixture()
        vm.call("eu5ab_naval_planner_run_recalculation_now")
        # Change the source after it has actually entered the async snapshot.
        for _ in range(50):
            if "eu5ab_naval_layout_source" in vm.vars[2]:
                break
            vm.call("eu5ab_naval_layout_tick")
        else:
            self.fail("No source snapshot")
        vm.buildings.pop((2, "local_governor"))
        vm.location_modifiers[2]["local_proximity_source"] -= 80
        self.finish_naval(vm)
        self.assertIn("eu5ab_naval_layout_failed", vm.vars[vm.ROOT])
        self.assertNotIn("eu5ab_naval_layout_has_results", vm.vars[vm.ROOT])

    def test_worker_finishes_both_jobs_and_shared_gui_has_separate_pages(self):
        vm = self.fixture()
        vm.call("eu5ab_governor_run_scheduled_planners")
        WorkerTimers(vm).advance(120)
        self.assertNotIn("eu5ab_governor_scan_active", vm.vars[vm.ROOT])
        self.assertNotIn("eu5ab_naval_planner_scan_active", vm.vars[vm.ROOT])
        gui = render_governor_gui()
        for prefix in ("eu5ab_layout_", "eu5ab_naval_layout_"):
            self.assertIn(prefix + "pagination", gui)
            for index in (1, 2, 3):
                self.assertIn(prefix + f"view_{index}_retained", gui)

    def test_all_ports_are_compared_and_short_lists_do_not_invent_targets(self):
        vm = self.fixture()
        for candidates in ({3, 5, 7, 9}, {3, 5}, set()):
            vm.naval_candidates = candidates
            vm.call("eu5ab_naval_planner_manual_recalculation")
            root = vm.vars[vm.ROOT]
            self.assertEqual(root["eu5ab_naval_layout_single_candidates"], len(candidates))
            self.assertEqual(root["eu5ab_naval_layout_candidate_count"], min(3, len(candidates)))
            self.assertEqual(root["eu5ab_naval_layout_result_count"], 4)
            if len(candidates) < 3:
                self.assertNotIn("eu5ab_naval_layout_candidate_3_to", root)

    def test_zero_negative_and_below_threshold_candidates_remain_visible(self):
        for target_value, percent, qualifies in ((100, 0, False), (99, 0, False),
                (179, 80, False), (179, 79, True), (179, 200, False), (179, 0, True)):
            with self.subTest(value=target_value, threshold=percent):
                vm = self.isolated([10, 100, target_value])
                root = vm.vars[vm.ROOT]
                root["eu5ab_global_naval_governor_migration_threshold_percent"] = percent
                vm.call("eu5ab_naval_layout_begin")
                self.finish_naval(vm)
                self.assertEqual(root["eu5ab_naval_layout_candidate_1_to"], 2)
                self.assertEqual("eu5ab_naval_layout_candidate_1_qualifies" in root, qualifies)
                self.assertEqual("eu5ab_naval_layout_result_proposal" in root, qualifies)
                self.assertEqual(vm.vars[1]["eu5ab_naval_layout_row_to"], 2 if qualifies else 1)

    def test_zero_contribution_and_equal_scores(self):
        vm = self.isolated([10, 100, 1], sources={0: 100, 1: 180})
        vm.call("eu5ab_naval_layout_begin")
        self.finish_naval(vm)
        root = vm.vars[vm.ROOT]
        self.assertEqual(root["eu5ab_naval_layout_candidate_1_before"], 0)
        self.assertIn("eu5ab_naval_layout_candidate_1_zero_base", root)
        self.assertNotIn("eu5ab_naval_layout_candidate_1_percent", root)
        self.assertIn("eu5ab_naval_layout_candidate_1_qualifies", root)
        vm = self.isolated([10, 100, 200, 200, 200], candidates=(2, 3, 4))
        vm.call("eu5ab_naval_layout_begin")
        self.finish_naval(vm)
        self.assertEqual([vm.vars[vm.ROOT][f"eu5ab_naval_layout_candidate_{n}_to"] for n in (1, 2, 3)], [2, 3, 4])

    def test_empty_existing_set_and_incomplete_work(self):
        vm = self.isolated([10, 100, 200], old=())
        vm.call("eu5ab_naval_layout_begin")
        self.finish_naval(vm)
        self.assertIn("eu5ab_naval_layout_ready", vm.vars[vm.ROOT])
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_naval_layout_result_count"], 0)
        with self.assertRaises(PropagationBudgetExceeded):
            plan_complete_layout({1}, {2}, {0: 100, 1: 80}, vm.locations, {}, {},
                                 capital=0, planner=NAVAL_PLANNER, max_steps=0)
        vm = self.fixture()
        vm.call("eu5ab_naval_planner_run_recalculation_now")
        while vm.vars[vm.ROOT]["eu5ab_naval_gov_refresh_phase"] > 0:
            vm.call("eu5ab_naval_layout_tick")
        vm.vars[vm.ROOT]["eu5ab_naval_layout_wave_budget"] = 0
        self.finish_naval(vm)
        self.assertIn("eu5ab_naval_layout_failed", vm.vars[vm.ROOT])
        self.assertNotIn("eu5ab_naval_layout_ready", vm.vars[vm.ROOT])

    def test_naval_threshold_gestures_default_and_registration_are_independent(self):
        setting = "eu5ab_global_naval_governor_migration_threshold_percent"
        key = "flag:eu5ab_regional_development__naval_governor_migration_threshold_percent"
        vm = self.isolated([10, 100, 200])
        root = vm.vars[vm.ROOT]
        root["eu5ab_global_governor_migration_threshold_percent"] = 37
        for saved, expected in ((None, 80), (0, 0), (200, 200)):
            vm.maps[vm.ROOT]["cmm"] = {} if saved is None else {key: saved}
            vm.call("eu5ab_naval_planner_initialize_threshold_setting")
            self.assertEqual(vm.maps[vm.ROOT]["cmm"][key], expected)
        for old in (0, 4, 80, 196, 200):
            for step in (-10, -5, -1, 1, 5, 10):
                raw = (200 if step > 0 else 0) if abs(step) == 10 else max(0, min(200, old+step))
                root[setting] = old
                vm.maps[vm.ROOT]["cmm"] = {key: raw}
                vm.call("eu5ab_naval_planner_adjust_threshold_step")
                self.assertEqual(vm.maps[vm.ROOT]["cmm"][key], max(0, min(200, old+step)))
                self.assertEqual(root["eu5ab_global_governor_migration_threshold_percent"], 37)
        self.assertEqual(GLOBAL_RULE_DEFAULTS["naval_governor_migration_threshold_percent"], 80)
        block = next(b for b in _blocks_for_token(render_on_actions(), "cmm_register_numeric_setting = ")
                     if "setting_id = naval_governor_migration_threshold_percent" in b)
        self.assertIn("min_value = 0 max_value = 200 step_value = 1", block)
        self.assertNotIn("governor_migration_enabled", block)

    def test_new_site_scores_all_ports_including_low_value_site_with_large_coverage(self):
        vm = TransportScriptVM(nodes=range(6), capital=0, edges=((2, 3), (3, 4), (4, 5)))
        vm.connected = {0}
        vm.naval_candidates = {2, 3, 4}
        vm.locations[2] = replace(vm.locations[2], population=200)
        vm.locations[3] = replace(vm.locations[3], population=100)
        vm.locations[5] = replace(vm.locations[5], population=10000)
        vm.country_modifiers["num_naval_governors"] = 1
        vm.call("eu5ab_naval_planner_manual_recalculation")
        root = vm.vars[vm.ROOT]
        self.assertEqual(root["eu5ab_naval_top_1"], 4)
        self.assertEqual({root[f"eu5ab_naval_top_{n}"] for n in (1, 2, 3)}, {2, 3, 4})

    def test_naval_gui_binds_all_actions_to_its_own_results(self):
        gui = render_governor_gui()
        start = gui.index('widget = {\n    name = "eu5ab_naval_layout_local_container"')
        naval = _blocks_for_token(gui[start:], "widget = ")[0]
        self.assertNotIn("eu5ab_gui_pan_local_governor_", naval)
        self.assertNotIn("'eu5ab_layout_", naval)
        self.assertIn("eu5ab_gui_pan_naval_governor_", naval)
        self.assertIn("align = center|nobaseline", naval)

    def test_transport_change_enrolls_both_types_and_local_schema_cleanup_is_isolated(self):
        vm = self.fixture()
        vm.call("eu5ab_governor_manual_recalculation")
        root = vm.vars[vm.ROOT]
        expected = self.published(vm, "eu5ab_naval_layout_")
        root.update(eu5ab_gov_transport_schema=1, eu5ab_naval_top_1=3,
                    eu5ab_naval_has_migration=1)
        vm.call("eu5ab_governor_check_transport_rules")
        self.assertEqual(expected, self.published(vm, "eu5ab_naval_layout_"))
        self.assertEqual(root["eu5ab_naval_top_1"], 3)
        self.assertIn("eu5ab_naval_has_migration", root)
        vm.advance_set = {"road_building"}
        root["eu5ab_governor_recalculation_scheduled"] = 1
        vm.call("eu5ab_prepare_governor_window")
        self.assertIn("eu5ab_governor_dirty", root)
        self.assertIn("eu5ab_naval_planner_dirty", root)

    def test_naval_transport_check_handles_missing_snapshot(self):
        vm = self.fixture()
        root = vm.vars[vm.ROOT]
        root.pop("eu5ab_naval_gov_transport_schema", None)
        root.pop("eu5ab_naval_gov_transport_road_tier", None)
        vm.call("eu5ab_naval_planner_check_transport_rules")
        self.assertIn("eu5ab_naval_planner_dirty", root)

        check = vm.definitions["eu5ab_naval_planner_check_transport_rules"]
        self.assertEqual([key for key, _, _ in check], ["if", "else_if", "else_if", "else_if"])
        self.assertIn("eu5ab_naval_gov_transport_schema", str(check[0]))
        self.assertIn("eu5ab_naval_gov_transport_road_tier", str(check[2]))

        recovery = vm.definitions["eu5ab_naval_layout_recover_transport_restart"]
        self.assertNotIn("eu5ab_naval_planner_recalculation_scheduled", str(recovery))
        self.assertNotIn("eu5ab_naval_planner_skip_next_scheduled_event", str(recovery))
