"""Percentage controls and below-threshold previews execute generated effects."""
import unittest
from dataclasses import replace

from src.eu5autobuild.generator import GLOBAL_RULE_DEFAULTS, render_on_actions
from src.eu5autobuild.governor_generator import render_governor_gui
from src.eu5autobuild.governor_layout_policy import plan_complete_layout
from src.eu5autobuild.governor_layout_ui import render_layout_scripted_guis
from tests._governor_script_vm import GovernorScriptVM, parse
from tests._generated import _blocks_for_token
from tests.test_governor_layout_policy import locations


SETTING = "eu5ab_global_governor_migration_threshold_percent"
KEY = "flag:eu5ab_regional_development__governor_migration_threshold_percent"


def fixture(values, old, candidates, sources=None):
    nodes = {n: replace(v, runtime_value=values[n]) for n, v in locations(len(values)).items()}
    sources = sources or {0: 100, **{n: 80 for n in old}}
    return GovernorScriptVM(nodes, {}, {}, sources, old, candidates, 0), nodes, sources


def sync_settings(vm):
    vm.execute([("eu5ab_sync_cmm_settings", "=", "yes")], [vm.ROOT])


class RelocationSettingsTests(unittest.TestCase):
    def test_relocation_master_defaults_on_without_overwriting_saved_choice(self):
        self.assertEqual(GLOBAL_RULE_DEFAULTS["governor_relocation_enabled"], 1)
        self.assertEqual(GLOBAL_RULE_DEFAULTS["governor_migration_enabled"], 0)
        vm, _, _ = fixture([10, 100, 185], {1}, {2})
        key = "flag:eu5ab_regional_development__governor_relocation_enabled"
        for saved, expected in ((None, 1), (0, 0), (1, 1)):
            vm.maps[vm.ROOT]["cmm"] = {} if saved is None else {key: saved}
            vm.call("eu5ab_governor_initialize_relocation_setting")
            self.assertEqual(vm.maps[vm.ROOT]["cmm"][key], expected)

    def test_manual_refresh_obeys_feature_switch_but_not_auto_switches(self):
        for feature in (0, 1):
            for automatic in (0, 1):
                for recommendations in (0, 1):
                    with self.subTest(feature=feature, automatic=automatic, recommendations=recommendations):
                        vm, _, _ = fixture([10, 100, 185], {1}, {2})
                        vm.cmm_settings.update(eu5ab_global_governor_relocation_enabled=feature,
                                               eu5ab_global_governor_migration_enabled=automatic,
                                               eu5ab_global_governor_recommendations_enabled=recommendations)
                        vm.call("eu5ab_governor_manual_recalculation")
                        root = vm.vars[vm.ROOT]
                        self.assertEqual("eu5ab_layout_has_results" in root, bool(feature))
                        self.assertEqual("eu5ab_layout_candidate_1_to" in root, bool(feature))
                        self.assertEqual("eu5ab_local_governor_relocation_alert" in vm.alerts, bool(feature))
                        self.assertEqual(vm.rows(), [(1, 2)] if feature else [])
                        self.assertEqual(vm.calls, ["eu5ab_governor_refresh_other_recommendations"])
                        self.assertNotIn("eu5ab_governor_scan_active", root)
                        self.assertNotIn("eu5ab_governor_manual_run", root)
                        self.assertNotIn("eu5ab_layout_failed", root)
                        for key, value in vm.cmm_settings.items():
                            self.assertEqual(root[key], value)

    def test_cmm_refresh_callback_preserves_results_after_its_second_settings_sync(self):
        vm, _, _ = fixture([10, 100, 185], {1}, {2})
        vm.cmm_settings["eu5ab_global_governor_migration_enabled"] = 0
        root = vm.vars[vm.ROOT]
        root["cmf_callback"] = "flag:eu5ab_regional_development__governor_refresh_now"
        callback = parse(_blocks_for_token(render_on_actions(), "eu5ab_on_cmf_callback = ")[0])[0][2]
        vm.definitions["test_cmm_callback"] = next(body for name, _, body in callback if name == "effect")
        vm.call("test_cmm_callback")
        self.assertIn("eu5ab_layout_has_results", root)
        self.assertIn("eu5ab_layout_show_candidates", root)
        self.assertEqual(vm.rows(), [(1, 2)])
        self.assertIn("eu5ab_local_governor_relocation_alert", vm.alerts)
        for _ in range(3):
            sync_settings(vm)
            vm.call("eu5ab_layout_tick")  # An idle worker must not clear results.
        vm.call("eu5ab_governor_run_recalculation_now")  # New-site-only automatic scan.
        self.assertIn("eu5ab_layout_has_results", root)
        self.assertIn("eu5ab_layout_show_candidates", root)
        self.assertEqual(vm.rows(), [(1, 2)])
        self.assertEqual(root["eu5ab_layout_candidate_1_to"], 2)
        self.assertNotIn("eu5ab_governor_scan_active", root)

    def test_switching_off_auto_stops_job_but_retains_last_completed_rows(self):
        vm, _, _ = fixture([10, 100, 185], {1}, {2})
        vm.call("eu5ab_governor_manual_recalculation")
        vm.call("eu5ab_governor_run_recalculation_now")
        root = vm.vars[vm.ROOT]
        self.assertIn("eu5ab_governor_scan_active", root)
        vm.cmm_settings["eu5ab_global_governor_migration_enabled"] = 0
        sync_settings(vm)
        self.assertNotIn("eu5ab_governor_scan_active", root)
        self.assertNotIn("eu5ab_layout_failed", root)
        self.assertIn("eu5ab_layout_has_results", root)
        self.assertEqual(vm.rows(), [(1, 2)])
        self.assertEqual(root["eu5ab_layout_candidate_1_to"], 2)

    def test_feature_off_clears_results_and_reenable_allows_manual_with_auto_off(self):
        vm, _, _ = fixture([10, 100, 185], {1}, {2})
        vm.call("eu5ab_governor_manual_recalculation")
        root = vm.vars[vm.ROOT]
        vm.cmm_settings.update(eu5ab_global_governor_relocation_enabled=0,
                               eu5ab_global_governor_migration_enabled=0)
        sync_settings(vm)
        for key in ("eu5ab_layout_has_results", "eu5ab_layout_show_candidates",
                    "eu5ab_layout_candidate_1_to"):
            self.assertNotIn(key, root)
        self.assertEqual(vm.rows(), [])
        vm.cmm_settings["eu5ab_global_governor_relocation_enabled"] = 1
        vm.call("eu5ab_governor_manual_recalculation")
        self.assertIn("eu5ab_layout_has_results", root)
        self.assertEqual(vm.rows(), [(1, 2)])
        self.assertEqual(root["eu5ab_global_governor_migration_enabled"], 0)

    def test_missing_saved_setting_defaults_to_eighty_but_explicit_zero_survives(self):
        vm, _, _ = fixture([10, 100, 150], {1}, {2})
        for existing, expected in ((None, 80), (0, 0), (75, 75), (200, 200)):
            vm.maps[vm.ROOT]["cmm"] = {} if existing is None else {KEY: existing}
            vm.call("eu5ab_governor_initialize_threshold_setting")
            self.assertEqual(vm.maps[vm.ROOT]["cmm"][KEY], expected)

    def test_setting_default_range_and_independent_registration(self):
        self.assertEqual(GLOBAL_RULE_DEFAULTS["governor_migration_threshold_percent"], 80)
        actions = render_on_actions()
        block = next(b for b in _blocks_for_token(actions, "cmm_register_numeric_setting = ")
                     if "setting_id = governor_migration_threshold_percent" in b)
        self.assertIn("default_value = 80", block)
        self.assertIn("min_value = 0 max_value = 200 step_value = 1", block)
        self.assertNotIn("governor_migration_enabled", block)
        hooks = _blocks_for_token(actions, "cmm_add_scripted_gui = ")
        for name in ("governor_migration_enabled", "governor_migration_threshold_percent"):
            self.assertTrue(any(f"setting_id = {name}\n" in b for b in hooks))
        callback = _blocks_for_token(actions, "eu5ab_on_cmf_callback = ")[0]
        self.assertIn(KEY, callback)
        self.assertLess(callback.index("eu5ab_governor_adjust_threshold_step = yes"),
                        callback.index("eu5ab_sync_cmm_settings = yes"))

    def test_manual_uses_new_cmm_percentage_with_auto_off(self):
        vm, _, _ = fixture([10, 100, 179], {1}, {2})
        root = vm.vars[vm.ROOT]
        root.update(eu5ab_global_governor_migration_enabled=0,
                    eu5ab_global_governor_recommendations_enabled=0)
        for percent, passes in ((80, False), (79, True), (0, True), (200, False)):
            with self.subTest(percent=percent):
                vm.cmm_settings = {SETTING: percent}
                vm.call("eu5ab_governor_manual_recalculation")
                self.assertNotIn("eu5ab_governor_scan_active", root)
                self.assertEqual(root["eu5ab_layout_result_threshold_percent"], percent)
                self.assertEqual("eu5ab_layout_result_proposal" in root, passes)
                self.assertEqual(root["eu5ab_layout_candidate_1_to"], 2)
                self.assertEqual("eu5ab_layout_candidate_1_qualifies" in root, passes)
                self.assertIn("eu5ab_layout_show_candidates", root)
                self.assertEqual("eu5ab_local_governor_relocation_alert" in vm.alerts, passes)
                self.assertEqual(root["eu5ab_global_governor_migration_enabled"], 0)

    def test_top_three_distinct_destinations_kept_below_threshold(self):
        vm, nodes, sources = fixture([10, 1000, 500, 750, 700, 550, 10], {1, 2}, {3, 4, 5, 6})
        vm.call("eu5ab_layout_begin")
        vm.finish()
        root = vm.vars[vm.ROOT]
        self.assertEqual(root["eu5ab_layout_threshold_percent"], 80)  # Old-save fallback.
        self.assertEqual(root["eu5ab_layout_candidate_count"], 3)
        self.assertNotIn("eu5ab_layout_result_proposal", root)
        plan = plan_complete_layout({1, 2}, {3, 4, 5, 6}, sources, nodes, {}, {}, capital=0)
        self.assertEqual([p["destination_id"] for p in plan["top_candidates"]], [3, 4, 5])
        for rank, candidate in enumerate(plan["top_candidates"], 1):
            p = f"eu5ab_layout_candidate_{rank}"
            self.assertEqual(root[p+"_from"], candidate["origin_id"])
            self.assertEqual(root[p+"_to"], candidate["destination_id"])
            self.assertEqual(vm.lists[vm.ROOT][p+"_list"], [candidate["destination_id"]])
            self.assertAlmostEqual(root[p+"_net"], candidate["net"], places=3)
            self.assertAlmostEqual(root[p+"_percent"], candidate["gain_percent"], places=3)
            self.assertNotIn(p+"_qualifies", root)

    def test_zero_percent_still_rejects_zero_or_negative_gain_but_shows_candidates(self):
        for target_value in (100, 99):
            vm, _, _ = fixture([10, 100, target_value], {1}, {2})
            root = vm.vars[vm.ROOT]
            root[SETTING] = 0
            vm.call("eu5ab_layout_begin")
            vm.finish()
            self.assertNotIn("eu5ab_layout_result_proposal", root)
            self.assertNotIn("eu5ab_layout_candidate_1_qualifies", root)
            self.assertEqual(root["eu5ab_layout_candidate_1_to"], 2)
            self.assertLessEqual(root["eu5ab_layout_candidate_1_net"], 0)

    def test_zero_original_contribution_never_divides_by_zero(self):
        vm, nodes, sources = fixture([10, 100, 1], {1}, {2}, sources={0: 100, 1: 180})
        vm.call("eu5ab_layout_begin")
        vm.finish()
        root = vm.vars[vm.ROOT]
        self.assertEqual(root["eu5ab_layout_candidate_1_before"], 0)
        self.assertIn("eu5ab_layout_candidate_1_zero_base", root)
        self.assertNotIn("eu5ab_layout_candidate_1_percent", root)
        self.assertIn("eu5ab_layout_candidate_1_qualifies", root)
        result = plan_complete_layout({1}, {2}, sources, nodes, {}, {}, capital=0)
        self.assertIsNone(result["top_candidates"][0]["gain_percent"])

    def test_failed_manual_retry_preserves_previous_completed_preview(self):
        vm, _, _ = fixture([10, 100, 150], {1}, {2})
        root = vm.vars[vm.ROOT]
        vm.call("eu5ab_governor_manual_recalculation")
        self.assertIn("eu5ab_layout_candidate_1_to", root)
        tick = vm.definitions["eu5ab_layout_tick"]
        vm.definitions["eu5ab_layout_tick"] = [("eu5ab_layout_abort", "=", "yes")]
        vm.call("eu5ab_governor_manual_recalculation")
        self.assertEqual(root["eu5ab_layout_candidate_1_to"], 2)
        self.assertEqual(vm.lists[vm.ROOT]["eu5ab_layout_candidate_1_list"], [2])
        self.assertIn("eu5ab_layout_failed", root)
        self.assertNotIn("eu5ab_governor_scan_active", root)
        vm.definitions["eu5ab_layout_tick"] = tick
        vm.candidates.clear()
        vm.call("eu5ab_governor_manual_recalculation")
        self.assertEqual(root["eu5ab_layout_candidate_count"], 0)

    def test_navigation_and_three_fixed_preview_cards(self):
        vm, _, _ = fixture([10, 100, 150], {1}, {2})
        vm.definitions.update({k: v for k, _, v in parse(render_layout_scripted_guis())})
        root = vm.vars[vm.ROOT]
        root["eu5ab_layout_has_results"] = True
        for tab in ("candidates", "new", "plan", "candidates"):
            vm.execute(next(v for k, _, v in vm.definitions[f"eu5ab_gui_layout_show_{tab}"] if k == "effect"), [vm.ROOT])
            self.assertEqual("eu5ab_layout_show_candidates" in root, tab == "candidates")
            self.assertEqual("eu5ab_layout_show_new" in root, tab == "new")
        gui = render_governor_gui()
        for rank in range(1, 4):
            card = next(b for b in _blocks_for_token(gui, "widget = ") if f'name = "eu5ab_layout_candidate_{rank}_card"' in b)
            self.assertIn('datacontext = "[Scope.GetLocation]"', card)
            self.assertIn('eu5ab_layout_candidate_fail', card)

    def test_numeric_gestures_and_clamping_without_affecting_reset(self):
        vm, _, _ = fixture([10, 100, 150], {1}, {2})
        root = vm.vars[vm.ROOT]
        for old in (0, 1, 4, 9, 80, 191, 196, 199, 200):
            for step in (-10, -5, -1, 1, 5, 10):
                with self.subTest(old=old, step=step):
                    # Native CMM shift emits min/max; Ctrl emits five steps.
                    raw = (200 if step > 0 else 0) if abs(step) == 10 else max(0, min(200, old+step))
                    root[SETTING] = old
                    vm.maps[vm.ROOT]["cmm"] = {KEY: raw}
                    vm.call("eu5ab_governor_adjust_threshold_step")
                    self.assertEqual(vm.maps[vm.ROOT]["cmm"][KEY], max(0, min(200, old+step)))
            root[SETTING] = old
            vm.maps[vm.ROOT]["cmm"] = {KEY: 80}
            vm.call("eu5ab_governor_adjust_threshold_step")
            self.assertEqual(vm.maps[vm.ROOT]["cmm"][KEY], 80)

if __name__ == "__main__":
    unittest.main()
