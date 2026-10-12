"""Queue teardown acceptance tests executing the generated effects.

Native economics and scan continuation are outside this harness. Location
cleanup, sorting, watchdog cancellation and load recovery run real scripts.
"""
from copy import deepcopy
import unittest

from tests import _generated as automation
from tests._governor_script_vm import parse
from tests.test_queue_recovery_runtime import QueueVM


CLEAR = "eu5ab_clear_engine_candidate_queue"
FINISH = "eu5ab_finish_engine_candidate_queue"
START = "eu5ab_start_engine_candidate_queue"
RECOVER = "eu5ab_recover_runtime_after_load"
PREPARE = "eu5ab_prepare_engine_candidate_queue"
WATCHDOG = "eu5ab_check_engine_candidate_queue_watchdog"
SORT = "eu5ab_sort_candidate_queue"
SORT_RGO = "eu5ab_sort_rgo_candidate_queue"
INDEXES = tuple(
    f"eu5ab_q_phase_{phase}_{suffix}"
    for phase in range(1, 9)
    for suffix in ("locations", "unsorted_locations", "rgo_locations", "rgo_unsorted_locations")
) + tuple(f"eu5ab_q_{suffix}" for suffix in (
    "approved_locations", "profit_locations",
))

# Representative saved candidate state, including every phase and GUI stage.
SCRATCH_VARS = dict.fromkeys((
    *(f"eu5ab_capacity_{field}" for field in (
        "used", "limit", "ready", "open", "factor", "requested", "worker_country",
    )),
    *(f"eu5ab_capacity_phase_{phase}_order{suffix}" for phase in range(1, 9) for suffix in ("", "_ready")),
    "eu5ab_location_candidate_staged", "eu5ab_action_taken",
    "eu5ab_cached_location_need_score", "eu5ab_cached_rgo_queue_score",
    *(f"eu5ab_q_{suffix}" for suffix in (
        "profit_best_actual", "profit_best_rank", "profit_done", "location_approved",
        "queue_before", "approved_cost", "approved_income", "approved_profit",
        "approved_build_kind", "approved_emergency_override", "material_market", "done_rgo",
        "profit_candidate_priority", "profit_candidate_magnitude", "profit_candidate_rank",
        "fire_requested",
    )),
), 1)
SCRATCH_LISTS = {
    name: ["building"] for name in (
        *(f"eu5ab_q_phase_{phase}_types" for phase in range(1, 9)),
        *(f"eu5ab_q_{suffix}" for suffix in (
            "done_types", "approved_types", "seen_types",
            "confirmed_types", "failed_types", "profit_best_types",
        )),
    )
}
PERSISTENT_VARS = {
    "eu5ab_policy_id": 3, "eu5ab_scan_bucket": 4,
    "eu5ab_template_coverage_owner": "country",
    "eu5ab_active_rgo_construction": 1,
    "eu5ab_recent_build_penalty": 12, "eu5ab_failure_cooldown": 2,
}
PERSISTENT_LISTS = {"eu5ab_active_building_types": ["building"]}


class CleanupVM(QueueVM):
    def __init__(self, effects, guis):
        super().__init__(effects, guis)
        for name in (
            CLEAR, FINISH, FINISH + '_live', START, RECOVER, PREPARE, WATCHDOG, SORT, SORT_RGO,
            "eu5ab_clear_location_candidate_state", "eu5ab_clear_location_worker_state",
            "eu5ab_clear_worker_screening",
            "eu5ab_clear_backfill_worker_state", "eu5ab_clear_backfill_scratch",
            "eu5ab_reset_engine_candidate_watchdog_progress",
            "eu5ab_expire_old_scan_month", "eu5ab_settle_saved_approvals",
        ):
            self.definitions[name] = parse(automation._blocks_for_token(
                effects, "\n" + name + " = ")[0])[0][2]
        for name in ("eu5ab_settle_scan_candidate_batch", "eu5ab_clear_scan_continuation",
                     "eu5ab_reset_committed_construction_demand"):
            self.stubs[name] = lambda: None
        self.vars[self.ROOT].update(
            eu5ab_q_active=1, eu5ab_q_fire=1,
            eu5ab_scan_registry_schema_version=1, eu5ab_runtime_schema_version=2,
            eu5ab_global_budget_remaining=700,
        )
        self.native['eu5ab_scan_month_current'] = True
        self.lists[self.ROOT]["eu5ab_active_project_locations"] = ["location"]
        self.seed("location")
        self.run("eu5ab_ensure_template_coverage", self.ROOT)

    def seed(self, location):
        self.owners[location] = self.ROOT
        self.vars[location] = {**PERSISTENT_VARS, **SCRATCH_VARS}
        self.vars[location]['eu5ab_capacity_worker_country'] = self.ROOT
        self.lists[location] = deepcopy({**PERSISTENT_LISTS, **SCRATCH_LISTS})

    def test(self, k, op, v, stack):
        if k == "always":
            return v == "yes"
        if k == "has_variable_list":
            return bool(self.lists[stack[-1]].get(v))
        return super().test(k, op, v, stack)


class QueueCleanupRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = automation.generated_fixture().effects
        cls.guis = automation.generated_fixture().scripted_guis

    def vm(self):
        return CleanupVM(self.effects, self.guis)

    def assert_clean(self, vm, locations=("location",)):
        for location in locations:
            self.assertEqual(vm.vars[location], PERSISTENT_VARS, location)
            self.assertEqual({k: v for k, v in vm.lists[location].items() if v},
                             PERSISTENT_LISTS, location)
        for name in INDEXES:
            self.assertFalse(vm.lists[vm.ROOT].get(name), name)
        self.assertNotIn("eu5ab_q_active", vm.vars[vm.ROOT])
        self.assertNotIn("eu5ab_q_fire", vm.vars[vm.ROOT])
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_global_budget_remaining"], 700)
        self.assertEqual(vm.lists[vm.ROOT]["eu5ab_active_project_locations"], ["location"])

    def test_all_indexes_clean_on_finish_and_replacement(self):
        # Sorted-only reproduces old saves: the sorter discarded unsorted indexes.
        for exit_effect in (FINISH, PREPARE):
            for index in INDEXES:
                with self.subTest(exit=exit_effect, index=index):
                    vm = self.vm()
                    vm.lists[vm.ROOT][index] = ["location"]
                    vm.run(exit_effect, vm.ROOT)
                self.assert_clean(vm)

    def test_load_preserves_queue_indexes_and_production_settlement(self):
        vm = self.vm()
        vm.vars['factory'] = {'eu5ab_pl_initialized': True, 'eu5ab_pl_output_floor': .4}
        vm.variable_maps['factory'] = {'eu5ab_pl_settled_output': {'goods:tools': .4}}
        before = deepcopy((vm.vars['factory'], vm.variable_maps['factory']))
        vm.vars[vm.ROOT]['eu5ab_pl_epoch'] = 7
        for index in INDEXES:
            vm.lists[vm.ROOT][index] = ['location']
        country_before = deepcopy((vm.vars, vm.lists))
        vm.run(RECOVER, vm.ROOT)
        self.assertEqual((vm.vars, vm.lists), country_before)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_pl_epoch'], 7)
        self.assertEqual((vm.vars['factory'], vm.variable_maps['factory']), before)

    def test_overlap_and_repeated_finish_are_idempotent(self):
        vm = self.vm()
        for index in INDEXES:
            vm.lists[vm.ROOT][index] = ["location"]
        vm.run(FINISH, vm.ROOT)
        self.assert_clean(vm)
        state = deepcopy((vm.vars, vm.lists))
        vm.run(FINISH, vm.ROOT)
        self.assertEqual((vm.vars, vm.lists), state)

    def test_failed_refill_preserves_whole_round_construction_result(self):
        for starts in (None, 0, 31, 35):
            with self.subTest(starts=starts):
                vm = self.vm()
                country = vm.vars[vm.ROOT]
                if starts is None:
                    country.pop("eu5ab_constructions_started_this_tick")
                else:
                    country["eu5ab_constructions_started_this_tick"] = starts
                expected = 1 if starts else 2
                # Include old saves with a stale diagnostic from the last batch.
                country["eu5ab_diag_built_this_run"] = 3 - expected
                country["eu5ab_q_staged"] = 1
                country["eu5ab_scan_refill_active"] = 1
                vm.stubs["trigger_event_silently"] = lambda: None
                vm.stubs["eu5ab_prepare_engine_priority_phase"] = lambda: None
                vm.run(START, vm.ROOT)
                self.assertEqual(country["eu5ab_diag_built_this_run"], expected)
                # Every candidate in this batch fails: no confirmed start added.
                vm.run(FINISH, vm.ROOT)
                self.assertEqual(country["eu5ab_diag_built_this_run"], expected)
                self.assertEqual(country.get("eu5ab_constructions_started_this_tick"), starts)

    def test_sort_limit_does_not_orphan_candidates(self):
        for sort_effect, prefix in ((SORT, ""), (SORT_RGO, "rgo_")):
            with self.subTest(sort=sort_effect):
                vm = self.vm()
                # Read the configured real cap and exceed it by one location.
                iterator = next(v for k, _, v in vm.definitions[sort_effect]
                                if k == "ordered_in_list")
                cap = int(dict((k, v) for k, _, v in iterator)["max"])
                locations = ["location"] + [f"extra_{n}" for n in range(cap)]
                for n, location in enumerate(locations):
                    vm.seed(location)
                    vm.vars[location]["eu5ab_cached_location_need_score"] = cap + 1 - n
                    for phase in range(1, 9):
                        vm.vars[location][f"eu5ab_capacity_phase_{phase}_order"] = cap + 1 - n
                    vm.vars[location]["eu5ab_cached_rgo_queue_score"] = cap + 1 - n
                unsorted = f"eu5ab_q_phase_5_{prefix}unsorted_locations"
                sorted_index = f"eu5ab_q_phase_5_{prefix}locations"
                vm.lists[vm.ROOT][unsorted] = locations.copy()
                vm.run(sort_effect, vm.ROOT)
                self.assertEqual(vm.lists[vm.ROOT][sorted_index], locations[:cap])
                self.assertEqual(vm.lists[vm.ROOT][unsorted], locations)
                self.assertIn("eu5ab_location_candidate_staged", vm.vars[locations[-1]])
                vm.run(FINISH, vm.ROOT)
                self.assert_clean(vm, locations)

    def test_unreachable_rgo_phases_are_absent_and_ordinary_late_phases_still_clean(self):
        vm = self.vm()
        vm.lists[vm.ROOT]['eu5ab_worker_pending_locations'] = ['location']
        vm.vars['location']['eu5ab_worker_active'] = 1
        for phase in range(9, 17):
            vm.lists[vm.ROOT][f'eu5ab_q_phase_{phase}_unsorted_locations'] = ['location']
        vm.run(SORT_RGO, vm.ROOT)
        for phase in range(9, 17):
            self.assertNotIn(f'eu5ab_q_phase_{phase}_rgo_locations', vm.lists[vm.ROOT])
        vm.run("eu5ab_clear_location_worker_state")
        vm.run(FINISH, vm.ROOT)
        self.assert_clean(vm)
        for phase in range(9, 17):
            self.assertFalse(vm.lists[vm.ROOT].get(f'eu5ab_q_phase_{phase}_unsorted_locations'))
            self.assertFalse(f'eu5ab_q_phase_{phase}_rgo_' in automation.generated_fixture().effects,
                             f'Unreachable RGO phase {phase} remains')
            self.assertFalse(f'eu5ab_worker_phase_{phase}_rgo' in automation.generated_fixture().effects,
                             f'Unreachable RGO worker phase {phase} remains')

    def test_watchdog_keeps_a_data_wait_without_erasing_the_saved_phase(self):
        vm = self.vm()
        vm.vars[vm.ROOT].pop('eu5ab_q_fire')
        vm.lists[vm.ROOT]['eu5ab_q_phase_5_locations'] = ['location']
        vm.vars[vm.ROOT].update(eu5ab_q_phase=5, eu5ab_q_processed=1,
                               eu5ab_q_approved=0, eu5ab_q_seen=0, eu5ab_q_confirmed=0,
                               eu5ab_q_waiting_data=1, eu5ab_q_data_day=1, eu5ab_q_data_commits=0)
        before = deepcopy(vm.lists)
        vm.run('eu5ab_reset_engine_candidate_watchdog_progress', vm.ROOT)
        for _ in range(4):
            vm.run(WATCHDOG, vm.ROOT)
        self.assertEqual(vm.lists, before)
        self.assertTrue(vm.vars[vm.ROOT]['eu5ab_q_active'])
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_phase'], 5)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_global_budget_remaining'], 700)

    def test_watchdog_cancellation_cleans_location_state(self):
        vm = self.vm()
        vm.lists[vm.ROOT]["eu5ab_q_phase_5_locations"] = ["location"]
        vm.vars[vm.ROOT].update(eu5ab_q_phase=5, eu5ab_q_processed=0,
                                eu5ab_q_seen=0, eu5ab_q_confirmed=0)
        vm.run("eu5ab_reset_engine_candidate_watchdog_progress", vm.ROOT)
        vm.run(WATCHDOG, vm.ROOT)
        self.assertIn("eu5ab_location_candidate_staged", vm.vars["location"])
        vm.run(WATCHDOG, vm.ROOT)
        self.assert_clean(vm)
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_diag_queue_state"], 5)

    def test_load_preserves_completed_worker_for_the_reducer(self):
        vm = self.vm()
        vm.vars[vm.ROOT].pop("eu5ab_q_active")
        vm.seed("pending")
        vm.vars["pending"].update(eu5ab_worker_active=1, eu5ab_worker_complete=1,
                                   eu5ab_worker_staged=1, eu5ab_worker_phase_5_rgo=1)
        vm.lists["pending"]["eu5ab_worker_phase_5_types"] = ["building"]
        vm.lists[vm.ROOT]["eu5ab_worker_pending_locations"] = ["pending"]
        before = deepcopy((vm.vars, vm.lists))
        vm.run(RECOVER, vm.ROOT)
        self.assertEqual((vm.vars, vm.lists), before)

    def test_indexed_location_cleans_after_ownership_change(self):
        vm = self.vm()
        vm.owners["location"] = "another_country"
        vm.lists[vm.ROOT]["eu5ab_q_phase_5_locations"] = ["location"]
        vm.run(FINISH, vm.ROOT)
        self.assert_clean(vm)

    def test_old_index_does_not_clear_new_owners_replacement_work(self):
        vm = self.vm()
        vm.owners['location'] = 'another_country'
        vm.vars['location']['eu5ab_capacity_worker_country'] = 'another_country'
        vm.lists[vm.ROOT]['eu5ab_q_phase_5_locations'] = ['location']
        before = deepcopy((vm.vars['location'], vm.lists['location']))
        vm.run(FINISH, vm.ROOT)
        self.assertEqual((vm.vars['location'], vm.lists['location']), before)
        self.assertFalse(vm.lists[vm.ROOT]['eu5ab_q_phase_5_locations'])


if __name__ == "__main__":
    unittest.main()
