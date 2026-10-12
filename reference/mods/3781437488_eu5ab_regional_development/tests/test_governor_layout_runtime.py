import unittest
import random
from dataclasses import replace

from src.eu5autobuild.governor_generator import render_governor_events
from src.eu5autobuild.governor_layout_policy import plan_complete_layout
from tests._governor_script_vm import GovernorScriptVM, parse
from tests.test_governor_layout_policy import locations


class LayoutRuntimeTests(unittest.TestCase):
    def test_exhausted_planned_land_source_does_not_visit_zero_boundary_nodes(self):
        nodes = locations(3)
        vm = GovernorScriptVM(nodes, {0: {1}, 1: {0, 2}, 2: {1}}, {},
                              {0: 100}, {1}, {2}, 0)
        vm.call('eu5ab_layout_begin')
        vm.call('eu5ab_layout_reset_wave')
        root = vm.vars[vm.ROOT]
        root.update(eu5ab_gov_queue_head=0, eu5ab_gov_queue_tail=0,
                    eu5ab_layout_pending_nodes=1)
        vm.vars[0].update(eu5ab_gov_predicted=20, eu5ab_gov_planned_road_cost=40)
        vm.call('eu5ab_layout_relax_one_planned')
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_gov_eval_locations'], [])
        self.assertNotIn('eu5ab_gov_queue_head', root)
        self.assertEqual(root['eu5ab_layout_wave_work'], 1)
        self.assertEqual(root['eu5ab_layout_total_work'], 1)
        self.assertNotIn('eu5ab_layout_source_prediction', vm.local)

    def four_seat_swap_fixture(self):
        nodes = locations(6)
        for n, value in enumerate((100, 10000, 9000, 8000, 1000, 1850)):
            nodes[n] = replace(nodes[n], runtime_value=value)
        return GovernorScriptVM(nodes, {}, {}, {0: 100, 1: 80, 2: 80, 3: 80, 4: 80},
                                {1, 2, 3, 4}, {5}, 0)

    def test_ordered_effect_defaults_to_one_and_requires_explicit_max_for_all(self):
        for maximum, expected in (("", 1), ("max = 6", 6)):
            with self.subTest(maximum=maximum):
                vm = self.four_seat_swap_fixture()
                vm.definitions["test_ordered"] = parse(f"""
                    ordered_owned_location = {{
                        order_by = 0 {maximum}
                        set_variable = eu5ab_test_visited
                    }}
                """)
                vm.call("test_ordered")
                self.assertEqual(sum("eu5ab_test_visited" in data for data in vm.vars.values()), expected)

    def test_four_seat_swap_publishes_complete_plan_and_matches_candidate_gain(self):
        vm = self.four_seat_swap_fixture()
        root = vm.vars[vm.ROOT]
        for _ in range(2):  # Repeated refresh must replace, not truncate, the rows.
            vm.call("eu5ab_governor_manual_recalculation")
            self.assertEqual(vm.rows(), [(1, 1), (2, 2), (3, 3), (4, 5)])
            self.assertEqual(root["eu5ab_layout_result_count"], 4)
            self.assertEqual(root["eu5ab_layout_page_count"], 2)
            self.assertEqual(root["eu5ab_layout_validated_moves"], 1)
            self.assertNotIn("eu5ab_layout_invalid_rows", root)
            self.assertEqual(root["eu5ab_layout_result_before"], 22400)
            self.assertEqual(root["eu5ab_layout_result_after"], 23080)
            self.assertEqual(root["eu5ab_layout_candidate_1_before"], 800)
            self.assertEqual(root["eu5ab_layout_candidate_1_after"], 1480)
            self.assertEqual(root["eu5ab_layout_result_net"], root["eu5ab_layout_candidate_1_net"])
            for rank in (1, 2, 3):
                self.assertIn(f"eu5ab_layout_view_{rank}_retained", root)
            root["eu5ab_layout_page"] = 1
            vm.call("eu5ab_layout_refresh_page")
            self.assertEqual((root["eu5ab_layout_view_1_from"], root["eu5ab_layout_view_1_to"]), (4, 5))
            self.assertNotIn("eu5ab_layout_view_1_retained", root)
            self.assertNotIn("eu5ab_layout_view_2_from", root)

    def test_saved_taihe_swap_republishes_all_four_rows(self):
        # Publication fields from the user's 1436.4.1 save; no map/model rerun.
        old = {10301, 10396, 11019, 11857}
        selected = {10301, 10396, 10854, 11857}
        base = locations(1)[0]
        nodes = {n: replace(base, id=n) for n in sorted(old | selected)}
        vm = GovernorScriptVM(nodes, {}, {}, {}, old, {10854}, 10301)
        root = vm.vars[vm.ROOT]
        root.update(eu5ab_layout_seats=4, eu5ab_layout_result_count=1,
                    eu5ab_layout_qualifies=1, eu5ab_layout_proposal_kind=2,
                    eu5ab_layout_result_before=14504.61159,
                    eu5ab_layout_result_after=15789.98224,
                    eu5ab_layout_result_net=1285.37065)
        bands = {10301: -1, 10396: -1, 10854: -2, 11019: -3, 11857: -2}
        for n in nodes:
            vm.vars[n]["eu5ab_layout_band_order"] = bands[n]
            # Only Taihe is unmatched, so distance cannot change the pairing.
            vm.vars[n]["eu5ab_layout_distance"] = 0
            if n in old:
                vm.vars[n]["eu5ab_layout_old"] = 1
            if n in selected:
                vm.vars[n]["eu5ab_layout_selected"] = 1
                vm.vars[n]["eu5ab_layout_display"] = 1
        vm.vars[10301].update(eu5ab_layout_row_order=1, eu5ab_layout_row_to=10301)
        vm.call("eu5ab_layout_validate_rows")
        self.assertIn("eu5ab_layout_invalid_rows", root)
        vm.call("eu5ab_layout_publish_rows")
        vm.call("eu5ab_layout_validate_rows")
        vm.call("eu5ab_layout_refresh_page")
        self.assertNotIn("eu5ab_layout_invalid_rows", root)
        self.assertEqual(vm.rows(), [(10301, 10301), (10396, 10396),
                                     (11019, 10854), (11857, 11857)])
        self.assertEqual(root["eu5ab_layout_result_count"], 4)
        self.assertEqual(root["eu5ab_layout_page_count"], 2)
        self.assertEqual(root["eu5ab_layout_validated_moves"], 1)
        self.assertEqual(root["eu5ab_layout_result_net"], 1285.37065)
        self.assertNotIn("eu5ab_layout_view_3_retained", root)
        root["eu5ab_layout_page"] = 1
        vm.call("eu5ab_layout_refresh_page")
        self.assertEqual(root["eu5ab_layout_view_1_from"], 11857)
        self.assertIn("eu5ab_layout_view_1_retained", root)

    def test_incomplete_or_mismatched_rows_cannot_publish_scores_or_alerts(self):
        corruptions = {
            "missing_ordered_max": None,
            "missing_row": "ordered_owned_location = { limit = { has_variable = eu5ab_layout_old } order_by = 0 max = 1 remove_variable = eu5ab_layout_row_order }",
            "missing_target": "ordered_owned_location = { limit = { has_variable = eu5ab_layout_old } order_by = 0 max = 1 remove_variable = eu5ab_layout_row_to }",
            "duplicate_target": "every_owned_location = { limit = { has_variable = eu5ab_layout_old } set_variable = { name = eu5ab_layout_row_to value = 1 } }",
            "wrong_count": "set_variable = { name = eu5ab_layout_result_count value = 1 }",
            "missing_display": "ordered_owned_location = { limit = { has_variable = eu5ab_layout_display } order_by = 0 max = 1 remove_variable = eu5ab_layout_display }",
            "positive_gain_without_moves": """
                every_owned_location = {
                    remove_variable = eu5ab_layout_display
                    if = {
                        limit = { has_variable = eu5ab_layout_old }
                        set_variable = eu5ab_layout_display
                        set_variable = { name = eu5ab_layout_row_to value = this }
                    }
                }
            """,
        }
        for case, corruption in corruptions.items():
            with self.subTest(case=case):
                vm = self.four_seat_swap_fixture()
                publisher = vm.definitions["eu5ab_layout_publish_rows"]
                if corruption is None:
                    ordered = next(body for key, _, body in publisher if key == "ordered_owned_location")
                    ordered[:] = [entry for entry in ordered if entry[0] != "max"]
                else:
                    publisher.extend(parse(corruption))
                vm.call("eu5ab_governor_manual_recalculation")
                root = vm.vars[vm.ROOT]
                self.assertIn("eu5ab_layout_invalid_rows", root)
                self.assertIn("eu5ab_layout_failed", root)
                self.assertNotIn("eu5ab_layout_has_results", root)
                self.assertNotIn("eu5ab_layout_result_proposal", root)
                self.assertNotIn("eu5ab_governor_scan_active", root)
                self.assertNotIn("eu5ab_local_governor_relocation_alert", vm.alerts)
                self.assertNotIn(("cmf_show_alert", "eu5ab_local_governor_relocation_alert"), vm.alert_actions)
                self.assertEqual(root["eu5ab_layout_result_net"], 0)
                self.assertEqual(vm.rows(), [])

    def test_below_threshold_plan_keeps_all_seats_without_improvement(self):
        vm = self.four_seat_swap_fixture()
        root = vm.vars[vm.ROOT]
        root["eu5ab_global_governor_migration_threshold_percent"] = 200
        vm.call("eu5ab_governor_manual_recalculation")
        self.assertEqual(vm.rows(), [(1, 1), (2, 2), (3, 3), (4, 4)])
        self.assertEqual(root["eu5ab_layout_result_count"], 4)
        self.assertEqual(root["eu5ab_layout_validated_moves"], 0)
        self.assertNotIn("eu5ab_layout_invalid_rows", root)
        self.assertNotIn("eu5ab_layout_result_proposal", root)
        self.assertEqual(root["eu5ab_layout_result_net"], 0)
        self.assertEqual(root["eu5ab_layout_result_before"], root["eu5ab_layout_result_after"])

    def test_manual_plan_alerts_on_first_pass_despite_disabled_auto_and_cooldown(self):
        nodes = locations(3)
        nodes[1] = replace(nodes[1], runtime_value=1000)
        nodes[2] = replace(nodes[2], runtime_value=1850)
        vm = GovernorScriptVM(nodes, {}, {}, {0: 100, 1: 80}, {1}, {2}, 0)
        root = vm.vars[vm.ROOT]
        root.update(eu5ab_global_governor_recommendations_enabled=0,
                    eu5ab_global_governor_migration_enabled=0,
                    eu5ab_local_migration_cooldown=8)
        for _ in range(2):
            vm.call("eu5ab_governor_manual_recalculation")
            self.assertNotIn("eu5ab_governor_scan_active", root)
            self.assertEqual(vm.rows(), [(1, 2)])
            self.assertEqual(root["eu5ab_layout_result_net"], 680)
            self.assertIn("eu5ab_local_governor_relocation_alert", vm.alerts)
            self.assertEqual(root["eu5ab_local_migration_cooldown"], 8)
            self.assertNotIn("eu5ab_governor_manual_run", root)
            vm.alerts.clear()

    def test_manual_failure_clears_override_and_cannot_publish_stale_plan(self):
        vm, _ = self.fixture()
        root = vm.vars[vm.ROOT]
        vm.definitions["eu5ab_layout_tick"] = [("eu5ab_layout_abort", "=", "yes")]
        vm.call("eu5ab_governor_manual_recalculation")
        self.assertNotIn("eu5ab_governor_manual_run", root)
        self.assertNotIn("eu5ab_layout_has_results", root)
        self.assertIn("eu5ab_layout_failed", root)
        self.assertNotIn("eu5ab_local_governor_relocation_alert", vm.alerts)

    def test_manual_job_survives_dirty_restart_without_enabling_auto(self):
        vm, _ = self.fixture()
        root = vm.vars[vm.ROOT]
        root.update(eu5ab_global_governor_recommendations_enabled=0,
                    eu5ab_global_governor_migration_enabled=0)
        # A manual job saved by an older version can still be resumed.
        root["eu5ab_governor_manual_run"] = True
        vm.call("eu5ab_governor_run_recalculation_now")
        root["eu5ab_governor_dirty"] = True
        while root["eu5ab_layout_phase"] != 5:
            vm.call("eu5ab_layout_tick")
        vm.call("eu5ab_layout_publish")
        self.assertIn("eu5ab_governor_manual_run", root)
        self.assertEqual(root["eu5ab_layout_ticks"], 0)
        vm.finish()
        self.assertNotIn("eu5ab_governor_manual_run", root)
        self.assertNotIn("eu5ab_layout_failed", root)
        self.assertEqual(root["eu5ab_global_governor_recommendations_enabled"], 0)

    def test_legacy_transport_job_restarts_without_publishing_old_work(self):
        for entry in ("eu5ab_layout_tick", "eu5ab_layout_publish"):
            with self.subTest(entry=entry):
                vm, _ = self.fixture()
                vm.call("eu5ab_layout_begin")
                root = vm.vars[vm.ROOT]
                root.update(eu5ab_gov_transport_schema=1,
                            eu5ab_governor_recalculation_scheduled=1,
                            eu5ab_layout_confirmation_streak=2,
                            eu5ab_local_migration_cooldown=7,
                            eu5ab_layout_has_results=1,
                            eu5ab_layout_result_before=999)
                vm.call(entry)
                self.assertEqual(vm.calls, ["eu5ab_governor_refresh_other_recommendations"])
                self.assertEqual(root["eu5ab_gov_transport_schema"], 2)
                self.assertEqual(root["eu5ab_layout_phase"], 12)
                self.assertEqual(root["eu5ab_layout_ticks"], 0)
                self.assertNotIn("eu5ab_layout_has_results", root)
                self.assertNotIn("eu5ab_layout_confirmation_streak", root)
                self.assertEqual(root["eu5ab_layout_result_before"], 999)
                self.assertEqual(root["eu5ab_local_migration_cooldown"], 7)
                self.assertIn("eu5ab_governor_skip_next_scheduled_event", root)
                self.assertEqual(len(vm.scheduled_events), 1)
                self.assertNotIn("eu5ab_governor_manual_run", root)

    def test_road_unlock_invalidates_active_plan_and_preserves_published_tier(self):
        vm, _ = self.fixture()
        vm.call("eu5ab_layout_begin")
        root = vm.vars[vm.ROOT]
        root["eu5ab_layout_result_road_tier"] = 0
        vm.highest_road_tier = 4
        vm.call("eu5ab_layout_tick")
        self.assertIn("eu5ab_governor_dirty", root)
        self.assertEqual(root["eu5ab_layout_result_road_tier"], 0)
        vm.call("eu5ab_layout_publish")
        self.assertEqual(vm.calls, ["eu5ab_governor_refresh_other_recommendations"])
        self.assertEqual(root["eu5ab_gov_transport_road_tier"], 4)
        self.assertEqual(root["eu5ab_layout_result_road_tier"], 0)
        vm.finish()
        self.assertEqual(root["eu5ab_layout_result_road_tier"], 4)

    def test_single_swap_survives_a_losing_full_plan(self):
        nodes = locations(5)
        for node, weight in {0: 1, 1: 2000, 2: 20, 3: 20, 4: 20000}.items():
            nodes[node] = replace(nodes[node], runtime_value=weight)
        graph = {n: {m for m in (n-1, n+1) if m in nodes} for n in nodes}
        vm = GovernorScriptVM(nodes, graph, {}, {0: 100, 2: 80, 4: 80},
                              {2, 4}, {1, 3}, 0)
        vm.call("eu5ab_layout_begin")
        vm.finish()
        root = vm.vars[vm.ROOT]
        # Hand-checkable 40-cost line: moving 2 -> 1 gains 400 at 1,
        # loses 8 at 2, and retains the valuable 80-point source at 4.
        self.assertEqual(vm.rows(), [(2, 1), (4, 4)])
        self.assertAlmostEqual(root["eu5ab_layout_result_net"], 392)
        self.assertAlmostEqual(root["eu5ab_layout_changed_contribution"], 12)
        self.assertNotIn("eu5ab_layout_full_qualifies", root)
        self.assertEqual(root["eu5ab_layout_result_kind"], 2)
        self.assertAlmostEqual(root["eu5ab_layout_single_destination_gain"], 404)
        for node in vm.vars.values():
            self.assertNotIn("eu5ab_layout_row_gain", node)
            self.assertNotIn("eu5ab_layout_planning_gain", node)
        self.assertEqual(root["eu5ab_layout_single_candidates"], 2)
        self.assertEqual(root["eu5ab_layout_single_comparisons"], 4)
        self.assertLess(root["eu5ab_layout_result_net"], root["eu5ab_layout_before"] * .2)
        self.assertEqual(root["eu5ab_layout_confirmation_streak"], 1)
        vm.call("eu5ab_layout_begin")
        vm.finish()
        self.assertIn("eu5ab_local_governor_relocation_alert", vm.alerts)
        self.assertEqual(root["eu5ab_local_migration_cooldown"], 12)

    def test_single_gain_identity_matches_direct_source_removal_with_overlap(self):
        nodes = {n: replace(v, runtime_value=1000 + n * 700)
                 for n, v in locations(7).items()}
        graph = {n: {m for m in (n-1, n+1) if m in nodes} for n in nodes}
        sources, old, vacant = {0: 100, 2: 140, 4: 80, 6: 50}, {2, 4}, {1, 3, 5}

        def coverage(seeds):
            # Independent oracle for this uniform 40-cost line, with no
            # dependency on the layout planner or propagation reference code.
            return {n: max([0] + [min(100, amount) - 40 * abs(n-source)
                                 for source, amount in seeds.items()]) for n in nodes}

        current = coverage(sources)
        expected = 0
        losses = {}
        for origin in old:
            removed = {**sources, origin: sources[origin]-80}
            without = coverage(removed)
            loss = sum((current[n]-without[n]) * nodes[n].runtime_value / 100 for n in nodes)
            losses[origin] = loss
            for target in vacant:
                replacement = coverage({**removed, target: sources.get(target, 0)+80})
                net = sum((replacement[n]-current[n]) * nodes[n].runtime_value / 100 for n in nodes)
                if net > 0 and net >= .80*loss:
                    expected = max(expected, net)
        vm = GovernorScriptVM(nodes, graph, {}, sources, old, vacant, 0)
        vm.call("eu5ab_layout_begin")
        vm.finish()
        for origin in old:
            self.assertAlmostEqual(vm.vars[origin]["eu5ab_layout_exclusive"], losses[origin])
        self.assertAlmostEqual(vm.vars[vm.ROOT]["eu5ab_layout_single_net"], expected)
        self.assertEqual(vm.vars[2]["eu5ab_layout_base"], 60)
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_layout_single_comparisons"], len(old)*len(vacant))

    def test_local_percentage_is_inclusive_without_fixed_floor(self):
        for origin_weight, target_weight, qualifies in (
            (100, 179.999, False), (100, 180, True),
            (1000, 1799.999, False), (1000, 1800, True),
        ):
            with self.subTest(origin_weight=origin_weight, target_weight=target_weight):
                nodes = locations(4)
                for node, weight in {0: 1, 1: origin_weight, 2: target_weight, 3: 1000000}.items():
                    nodes[node] = replace(nodes[node], runtime_value=weight)
                vm = GovernorScriptVM(nodes, {}, {}, {0: 100, 1: 80, 3: 80},
                                      {1, 3}, {2}, 0)
                vm.call("eu5ab_layout_begin")
                vm.finish()
                self.assertEqual("eu5ab_layout_result_proposal" in vm.vars[vm.ROOT], qualifies)
                self.assertEqual({to for _, to in vm.rows()}, {2, 3} if qualifies else {1, 3})
                self.assertEqual(vm.vars[vm.ROOT]["eu5ab_layout_single_candidates"], 1)

    def test_equally_good_single_swap_does_not_replace_qualifying_full_plan(self):
        nodes = locations(3)
        nodes[1] = replace(nodes[1], runtime_value=1000)
        nodes[2] = replace(nodes[2], runtime_value=1850)
        vm = GovernorScriptVM(nodes, {}, {}, {0: 100, 1: 80}, {1}, {2}, 0)
        vm.call("eu5ab_layout_begin")
        vm.finish()
        root = vm.vars[vm.ROOT]
        self.assertEqual(root["eu5ab_layout_single_net"], 680)
        self.assertEqual(root["eu5ab_layout_result_net"], 680)
        self.assertEqual(root["eu5ab_layout_result_kind"], 1)

    def test_extra_reductions_are_batched_to_64_locations_or_origins(self):
        vm, _ = self.fixture(count=90)
        vm.call("eu5ab_layout_begin")
        root = vm.vars[vm.ROOT]
        while root["eu5ab_layout_phase"] != 6:
            vm.call("eu5ab_layout_tick")
        vm.call("eu5ab_layout_tick")
        self.assertEqual(root["eu5ab_layout_pending_nodes"], 26)
        self.assertEqual(root["eu5ab_layout_phase"], 6)
        vm.call("eu5ab_layout_tick")
        self.assertEqual(root["eu5ab_layout_pending_nodes"], 0)
        self.assertEqual(root["eu5ab_layout_phase"], 3)

        vm, _ = self.fixture(count=70, old=range(1, 69), candidates={69})
        vm.call("eu5ab_layout_begin")
        root = vm.vars[vm.ROOT]
        while root["eu5ab_layout_phase"] in (12, 13):
            vm.call("eu5ab_layout_tick")
        root.update(eu5ab_layout_phase=8, eu5ab_layout_single_pending=68,
                    eu5ab_layout_candidate=69, eu5ab_layout_single_common=3,
                    eu5ab_layout_resume_phase=7)
        vm.call("eu5ab_layout_tick")
        self.assertEqual(root["eu5ab_layout_single_comparisons"], 64)
        self.assertEqual(root["eu5ab_layout_single_pending"], 4)
        self.assertEqual(root["eu5ab_layout_phase"], 8)

    def test_dirty_publish_refreshes_synchronous_consumer_before_restarting(self):
        vm, _ = self.fixture()
        vm.call("eu5ab_governor_run_recalculation_now")
        root = vm.vars[vm.ROOT]
        root.update(eu5ab_layout_confirmation_streak=2,
                    eu5ab_local_migration_cooldown=7,
                    eu5ab_layout_result_before=999)
        for _ in range(3):
            vm.call("eu5ab_governor_run_recalculation_now")
        self.assertEqual(len(vm.calls), 1)
        while root["eu5ab_layout_phase"] != 5:
            vm.call("eu5ab_layout_tick")
        vm.call("eu5ab_layout_publish")
        # The VM records this consumer boundary; it does not execute card
        # scoring, and this test makes no claim about engine score accuracy.
        self.assertEqual(vm.calls, ["eu5ab_governor_refresh_other_recommendations"] * 2)
        self.assertNotIn("eu5ab_governor_dirty", root)
        self.assertIn("eu5ab_governor_scan_active", root)
        self.assertEqual(root["eu5ab_layout_confirmation_streak"], 2)
        self.assertEqual(root["eu5ab_local_migration_cooldown"], 7)
        self.assertEqual(root["eu5ab_layout_result_before"], 999)
        self.assertEqual(len(vm.scheduled_events), 1)
        vm.finish()
        self.assertEqual(len(vm.calls), 2)
        self.assertEqual(root["eu5ab_governor_months_since_refresh"], 0)

    def test_another_change_after_restart_refreshes_again_without_extra_watchdog(self):
        vm, _ = self.fixture()
        vm.call("eu5ab_layout_begin")
        for expected_refreshes in (1, 2):
            vm.call("eu5ab_governor_run_recalculation_now")
            while vm.vars[vm.ROOT]["eu5ab_layout_phase"] != 5:
                vm.call("eu5ab_layout_tick")
            vm.call("eu5ab_layout_publish")
            self.assertEqual(len(vm.calls), expected_refreshes)
            self.assertNotIn("eu5ab_governor_dirty", vm.vars[vm.ROOT])
            self.assertEqual(len(vm.scheduled_events), 1)
        vm.finish()
        self.assertEqual(len(vm.calls), 2)

    def test_dirty_structural_abort_does_not_run_the_restart_pipeline(self):
        vm, _ = self.fixture()
        vm.call("eu5ab_layout_begin")
        root = vm.vars[vm.ROOT]
        root.update(eu5ab_governor_dirty=1, eu5ab_governor_months_since_refresh=8)
        vm.owners[11] = "other_country"
        vm.call("eu5ab_layout_publish")
        self.assertEqual(vm.calls, [])
        self.assertIn("eu5ab_layout_failed", root)
        self.assertNotIn("eu5ab_governor_scan_active", root)
        self.assertEqual(root["eu5ab_governor_months_since_refresh"], 8)

    def test_pending_event_keeps_its_existing_skip_or_dirty_semantics(self):
        for skip in (False, True):
            with self.subTest(skip=skip):
                vm, _ = self.fixture()
                vm.call("eu5ab_layout_begin")
                root = vm.vars[vm.ROOT]
                root.update(eu5ab_governor_dirty=1,
                            eu5ab_governor_recalculation_scheduled=1)
                if skip:
                    root["eu5ab_governor_skip_next_scheduled_event"] = 1
                # Supply the generated cleanup at the synchronous consumer's
                # entry, which this VM otherwise stubs. It must run before
                # layout_begin rebuilds the shared work lists.
                pipeline = "eu5ab_recalculate_governor_recommendations"
                vm.definitions[pipeline] = [
                    ("eu5ab_governor_clear_country_results", "=", "yes"),
                    *vm.definitions[pipeline],
                ]
                while root["eu5ab_layout_phase"] != 5:
                    vm.call("eu5ab_layout_tick")
                vm.call("eu5ab_layout_publish")
                self.assertEqual(len(vm.calls), 1)
                # Deliver the already queued event using its generated body.
                event = next(v for k, _, v in parse(render_governor_events())
                             if k == "eu5ab_governor.1")
                vm.definitions["test_deliver_pending_refresh"] = next(
                    v for k, _, v in event if k == "immediate")
                vm.call("test_deliver_pending_refresh")
                self.assertNotIn("eu5ab_governor_recalculation_scheduled", root)
                self.assertNotIn("eu5ab_governor_skip_next_scheduled_event", root)
                self.assertEqual("eu5ab_governor_dirty" in root, not skip)
                self.assertEqual(len(vm.calls), 1)
                self.assertEqual(len(vm.scheduled_events), 1)
                vm.finish()
                self.assertEqual(len(vm.calls), 1 if skip else 2)

    def test_watchdog_finishes_without_gui_and_matches_reference(self):
        vm, reference = self.fixture()
        vm.call("eu5ab_layout_begin")
        root = vm.vars[vm.ROOT]
        self.assertEqual(root["eu5ab_layout_total_work"], 0)
        for _ in range(100):
            vm.call("eu5ab_layout_watchdog")
            if "eu5ab_governor_scan_active" not in root:
                break
        self.assertNotIn("eu5ab_governor_scan_active", root)
        self.assertGreater(root["eu5ab_layout_fallback_batches"], 0)
        self.assertAlmostEqual(root["eu5ab_layout_result_net"], reference["modeled_net"], places=2)
        self.assertNotIn("eu5ab_layout_watchdog_scheduled", root)

    def test_watchdog_skips_work_when_gui_advanced_and_limits_stalled_batch(self):
        vm, _ = self.fixture(count=90)
        vm.call("eu5ab_layout_begin")
        vm.call("eu5ab_layout_tick")
        root = vm.vars[vm.ROOT]
        ticks = root["eu5ab_layout_ticks"]
        vm.call("eu5ab_layout_watchdog")
        self.assertEqual(root["eu5ab_layout_ticks"], ticks)
        self.assertEqual(root["eu5ab_layout_fallback_batches"], 0)
        vm.call("eu5ab_layout_watchdog")
        self.assertGreater(root["eu5ab_layout_ticks"], ticks)
        self.assertLessEqual(root["eu5ab_layout_ticks"] - ticks, 1)

    def test_legacy_scan_and_repeated_requests_keep_one_pending_watchdog(self):
        vm, _ = self.fixture()
        vm.call("eu5ab_layout_begin")
        root = vm.vars[vm.ROOT]
        root.pop("eu5ab_layout_ticks")
        root.pop("eu5ab_layout_watchdog_last_ticks")
        root.pop("eu5ab_layout_watchdog_scheduled")
        vm.scheduled_events = []
        vm.call("eu5ab_layout_schedule_watchdog")
        vm.call("eu5ab_layout_schedule_watchdog")
        vm.call("eu5ab_governor_manual_recalculation")
        self.assertEqual(len(vm.scheduled_events), 1)
        vm.call("eu5ab_layout_watchdog")
        self.assertGreater(root["eu5ab_layout_total_work"], 0)

    def test_watchdog_stops_after_disable_and_invalid_phase_aborts(self):
        vm, _ = self.fixture()
        vm.call("eu5ab_layout_begin")
        root = vm.vars[vm.ROOT]
        root["eu5ab_global_governor_migration_enabled"] = 0
        vm.call("eu5ab_layout_watchdog")
        self.assertNotIn("eu5ab_governor_scan_active", root)
        self.assertNotIn("eu5ab_layout_watchdog_scheduled", root)
        root["eu5ab_global_governor_migration_enabled"] = 1
        vm.call("eu5ab_layout_begin")
        root["eu5ab_layout_phase"] = 99
        vm.call("eu5ab_layout_watchdog")
        self.assertIn("eu5ab_layout_failed", root)
        self.assertNotIn("eu5ab_governor_scan_active", root)

    def test_migration_switch_skips_planner_but_keeps_initial_recommendation_pass(self):
        vm, _ = self.fixture()
        root = vm.vars[vm.ROOT]
        root.pop("eu5ab_global_governor_migration_enabled")
        root["eu5ab_naval_top_1"] = 4
        vm.call("eu5ab_governor_run_recalculation_now")
        self.assertEqual(vm.calls, ["eu5ab_governor_refresh_other_recommendations"])
        self.assertNotIn("eu5ab_layout_round", root)
        self.assertNotIn("eu5ab_governor_scan_active", root)
        self.assertEqual(root["eu5ab_naval_top_1"], 4)

    def test_relocation_feature_off_cancels_local_work_and_preserves_naval_card(self):
        vm, _ = self.fixture()
        vm.call("eu5ab_governor_run_recalculation_now")
        root = vm.vars[vm.ROOT]
        root.update(eu5ab_global_governor_relocation_enabled=0,
                    eu5ab_layout_has_results=1, eu5ab_layout_confirmation_streak=2,
                    eu5ab_naval_top_1=4)
        vm.call("eu5ab_layout_tick")
        for flag in ("eu5ab_governor_scan_active", "eu5ab_layout_has_results",
                     "eu5ab_layout_failed", "eu5ab_layout_confirmation_streak"):
            self.assertNotIn(flag, root)
        self.assertEqual(root["eu5ab_naval_top_1"], 4)
        root["eu5ab_global_governor_relocation_enabled"] = 1
        vm.call("eu5ab_governor_run_recalculation_now")
        self.assertIn("eu5ab_governor_scan_active", root)
        vm.finish()
        self.assertTrue(vm.rows())

    def fixture(self, count=12, old=(1,), candidates=None, roads=True):
        nodes = locations(count)
        # Distinct weights remove engine-iterator tie ambiguity.
        nodes = {n: replace(v, runtime_value=400+n*14) for n, v in nodes.items()}
        graph = {n: {m for m in (n-1, n+1) if m in nodes} for n in nodes}
        road_map = {frozenset((n, n+1)): "railroad" for n in range(count-1)} if roads else {}
        sources = {0: 100, **{n: 80 for n in old}}
        pool = set(range(1, count)) - set(old) if candidates is None else set(candidates)
        vm = GovernorScriptVM(nodes, graph, road_map, sources, old, pool, 0)
        reference = plan_complete_layout(old, pool, sources, nodes, graph, road_map, capital=0)
        return vm, reference

    def test_generated_queue_matches_reference_beyond_six_hops(self):
        vm, reference = self.fixture()
        vm.call("eu5ab_governor_run_recalculation_now")
        self.assertIn("eu5ab_governor_scan_active", vm.vars[vm.ROOT])
        self.assertEqual(vm.rows(), [])
        self.assertGreater(vm.finish(), 1)
        root = vm.vars[vm.ROOT]
        self.assertAlmostEqual(root["eu5ab_layout_result_net"], reference["modeled_net"], places=2)
        self.assertEqual({to for _, to in vm.rows()}, {s["destination_id"] for s in reference["display_steps"]})
        self.assertEqual(vm.calls, ["eu5ab_governor_refresh_other_recommendations"])

    def test_pagination_retains_all_four_origins(self):
        vm, reference = self.fixture(count=22, old=(1, 8, 14, 20))
        vm.call("eu5ab_layout_begin")
        vm.finish()
        self.assertEqual({n for n, _ in vm.rows()}, {1, 8, 14, 20})
        root = vm.vars[vm.ROOT]
        self.assertEqual(root["eu5ab_layout_page_count"], 2)
        self.assertEqual([root[f"eu5ab_layout_view_{n}_order"] for n in (1, 2, 3)], [1, 2, 3])
        root["eu5ab_layout_page"] = 1
        vm.call("eu5ab_layout_refresh_page")
        self.assertEqual(root["eu5ab_layout_view_1_order"], 4)
        self.assertNotIn("eu5ab_layout_view_2_from", root)
        self.assertEqual(vm.lists[vm.ROOT]["eu5ab_layout_view_2_list"], [])
        self.assertEqual({to for _, to in vm.rows()}, {s["destination_id"] for s in reference["display_steps"]})

    def test_budget_abort_does_not_publish_or_confirm_partial_results(self):
        vm, _ = self.fixture(count=80)
        vm.call("eu5ab_layout_begin")
        vm.vars[1].update(eu5ab_layout_row_order=1, eu5ab_layout_row_to=1)
        vm.vars[vm.ROOT]["eu5ab_layout_wave_budget"] = 1
        vm.finish()
        self.assertIn("eu5ab_layout_failed", vm.vars[vm.ROOT])
        self.assertEqual(vm.rows(), [(1, 1)])
        self.assertNotIn("eu5ab_layout_confirmation_streak", vm.vars[vm.ROOT])

    def test_one_pulse_does_not_drain_a_large_wave(self):
        vm, _ = self.fixture(count=90)
        vm.call("eu5ab_layout_begin")
        vm.call("eu5ab_layout_tick")
        self.assertEqual(sum("eu5ab_layout_source" in vm.vars[n] for n in vm.locations), 64)
        while vm.vars[vm.ROOT]["eu5ab_layout_phase"] in (12, 13):
            vm.call("eu5ab_layout_tick")
        vm.call("eu5ab_layout_tick")
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_layout_wave_work"], 64)
        self.assertIn("eu5ab_gov_queue_head", vm.vars[vm.ROOT])

    def test_manual_refresh_restarts_immediately_even_with_stale_active_flag(self):
        vm, _ = self.fixture()
        vm.call("eu5ab_layout_begin")
        vm.call("eu5ab_governor_manual_recalculation")
        self.assertEqual(vm.calls, ["eu5ab_governor_refresh_other_recommendations"])
        self.assertNotIn("eu5ab_governor_dirty", vm.vars[vm.ROOT])
        vm.finish()
        self.assertNotIn("eu5ab_governor_dirty", vm.vars[vm.ROOT])
        self.assertTrue(vm.rows())

    def test_disable_and_owner_change_prevent_publication(self):
        vm, _ = self.fixture()
        vm.call("eu5ab_layout_begin")
        vm.vars[vm.ROOT]["eu5ab_global_governor_recommendations_enabled"] = 0
        vm.finish()
        self.assertEqual(vm.rows(), [])
        vm.vars[vm.ROOT]["eu5ab_global_governor_recommendations_enabled"] = 1
        vm.call("eu5ab_layout_begin")
        vm.owners[11] = "other_country"
        vm.finish()
        self.assertEqual(vm.rows(), [])

        # A source can change after its batched validation but before commit.
        vm, _ = self.fixture()
        vm.call("eu5ab_layout_begin")
        while vm.vars[vm.ROOT]["eu5ab_layout_phase"] != 5:
            vm.call("eu5ab_layout_tick")
        vm.sources[1] += 1
        vm.call("eu5ab_layout_tick")
        self.assertIn("eu5ab_layout_failed", vm.vars[vm.ROOT])
        self.assertEqual(vm.rows(), [])

    def test_no_existing_seats_does_not_hide_new_slot_view(self):
        vm, _ = self.fixture(old=())
        vm.call("eu5ab_layout_begin")
        vm.finish()
        self.assertEqual(vm.rows(), [])
        self.assertNotIn("eu5ab_layout_has_results", vm.vars[vm.ROOT])
        self.assertNotIn("eu5ab_layout_invalid_rows", vm.vars[vm.ROOT])

    def test_generated_confirmation_uses_complete_target_set(self):
        vm, _ = self.fixture(count=16, old=(1, 2, 3, 4))
        vm.call("eu5ab_layout_begin")
        root = vm.vars[vm.ROOT]
        root["eu5ab_layout_qualifies"] = True
        for n in (5, 6, 7, 8):
            vm.vars[n]["eu5ab_layout_selected"] = n
        vm.call("eu5ab_layout_confirm")
        self.assertEqual(root["eu5ab_layout_confirmation_streak"], 1)
        del vm.vars[8]["eu5ab_layout_selected"]
        vm.vars[9]["eu5ab_layout_selected"] = 8
        vm.call("eu5ab_layout_confirm")
        self.assertEqual(root["eu5ab_layout_confirmation_streak"], 1)
        vm.call("eu5ab_layout_confirm")
        self.assertIn("eu5ab_local_governor_relocation_alert", vm.alerts)
        self.assertEqual(root["eu5ab_local_migration_cooldown"], 12)

    def test_lazy_generated_scoring_matches_full_reference_across_graphs(self):
        for seed in range(12):
            with self.subTest(seed=seed):
                # Seeded randomness reproduces test graphs; it is not used for security.
                rng = random.Random(seed)  # nosec B311
                nodes = {n: replace(v, runtime_value=rng.uniform(100, 5000)) for n, v in locations(18).items()}
                graph = {n: set() for n in nodes}
                road_map = {}
                for a, b in [(n, n+1) for n in range(17)] + [tuple(rng.sample(range(18), 2)) for _ in range(12)]:
                    graph[a].add(b)
                    graph[b].add(a)
                    road_map[frozenset((a, b))] = rng.choice(["gravel_road", "paved_road", "railroad"])
                old = set(rng.sample(range(1, 18), 4))
                sources = {0: 100, **{n: 80 for n in old}}
                pool = set(nodes)-old-{0}
                reference = plan_complete_layout(old, pool, sources, nodes, graph, road_map, capital=0)
                vm = GovernorScriptVM(nodes, graph, road_map, sources, old, pool, 0)
                vm.call("eu5ab_layout_begin")
                vm.finish()
                self.assertAlmostEqual(vm.vars[vm.ROOT]["eu5ab_layout_result_net"], reference["modeled_net"], places=2)
                self.assertEqual({to for _, to in vm.rows()}, {s["destination_id"] for s in reference["display_steps"]})


if __name__ == "__main__":
    unittest.main()
