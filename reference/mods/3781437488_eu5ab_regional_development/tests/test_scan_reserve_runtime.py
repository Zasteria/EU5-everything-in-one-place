"""Execute generated reserve, reducer, continuation and settlement branches.

Workers and native construction outcomes are injected. Country state, event
timing, lists, reserve arithmetic and queue cleanup execute from generated code.
These tests are not an EU5 engine simulation or a game performance benchmark.
"""
from collections import Counter
import unittest

from tests import _generated as automation
from tests._governor_script_vm import parse
from tests._automation_runtime import country_counter_initializers
from tests.test_scan_short_circuit_runtime import SCAN, ScanVM
from src.eu5autobuild.scan_reserve import REFILL_STALL_DAYS


MERGE = "eu5ab_merge_location_worker_results"
FINISH = "eu5ab_finish_engine_candidate_queue"
SETTLE = "eu5ab_settle_scan_candidate_batch"
TARGET = "eu5ab_update_scan_candidate_target"
REFILL = "eu5ab_refill_regional_development_scan"
PENDING = "eu5ab_scan_unscanned_locations"
RESERVE = "eu5ab_scan_candidate_reserve"


class ReserveVM(ScanVM):
    def __init__(self, definitions, parallel=0):
        super().__init__(definitions[SCAN], parallel=parallel)
        self.definitions.update(definitions)
        self.execute(self.definitions["test_country_counter_initializers"], [self.ROOT])
        self.vars[self.ROOT].update(
            eu5ab_scan_round_active=1, eu5ab_scan_active=1,
            eu5ab_global_enabled=1, eu5ab_monthly_build_quota=2,
            eu5ab_constructions_started_this_tick=0,
            eu5ab_deep_score_budget=40, eu5ab_scan_daily_task_limit=2,
            eu5ab_global_budget_remaining=1000,
            eu5ab_scan_backfill_enabled=1,
            eu5ab_scan_year=1410, eu5ab_scan_month=5,
        )
        self.lists[self.ROOT] = {}
        self.day, self.scheduled, self.dispatched, self.batches = 23, [], [], []
        self.accepted = set()
        self.worker_candidates = True
        self.material_commitments = 0
        self.call(TARGET)

    def test(self, k, op, v, stack):
        if k == "exists":
            return self.target(v, stack) is not None
        return super().test(k, op, v, stack)

    def execute(self, entries, stack):
        index = 0
        while index < len(entries):
            k, _, v = entries[index]
            end = index + 1
            if k == "if":
                while end < len(entries) and entries[end][0] in ("else_if", "else"):
                    end += 1
            data = {a: c for a, _, c in v} if isinstance(v, list) else {}
            if k == "trigger_event_silently" and "id" in data:
                self.scheduled.append((self.day + int(data["days"]), data["id"]))
            elif k in ("eu5ab_request_building_capacity", "eu5ab_run_location_worker") or (k == "trigger_event_silently" and "on_action" in data):
                # Inject successful GUI delivery here; the actual capture,
                # timeout and delayed-event paths have dedicated runtime tests.
                location = stack[-1]
                self.dispatched.append((self.day, location))
                if not self.worker_candidates:
                    self.vars[location].update(eu5ab_worker_complete=1, eu5ab_worker_staged=0)
                    index = end
                    continue
                self.vars[location].update(eu5ab_worker_complete=1,
                                          eu5ab_worker_staged=2,
                                          eu5ab_location_candidate_staged=1,
                                          eu5ab_worker_phase_7_rgo=1)
                # Two ordinary alternatives plus RGO must count as one location.
                self.lists[location]["eu5ab_worker_phase_5_types"] = ["building_a", "building_b"]
                for building in ("building_a", "building_b"):
                    self.vars.setdefault(building, {})
                    self.lists.setdefault(building, {})
            elif k == MERGE:
                self.execute(self.definitions[MERGE], stack)
            elif k == "eu5ab_reset_committed_construction_demand":
                self.material_commitments = 0
            elif k in ("eu5ab_hydrate_final_building_diagnostics", "eu5ab_request_candidate_quotes",
                       "eu5ab_clear_candidate_quotes", "eu5ab_clear_queue_bridge", "eu5ab_clear_winner_batch"):
                pass  # Quotation and native batch work are injected boundaries.
            elif k == "eu5ab_start_engine_candidate_queue":
                country = self.vars[self.ROOT]
                candidates = list(self.lists[self.ROOT].get("eu5ab_scan_candidate_locations", []))
                self.batches.append((self.day, candidates))
                country.update(eu5ab_q_active=1, eu5ab_diag_queue_state=2)
                for location in candidates:
                    if location in self.accepted and country.get("eu5ab_constructions_started_this_tick", 0) < country["eu5ab_monthly_build_quota"]:
                        country["eu5ab_constructions_started_this_tick"] = country.get("eu5ab_constructions_started_this_tick", 0) + 1
                        country["eu5ab_global_budget_remaining"] -= 10
                        self.material_commitments += 1
                self.execute(self.definitions[FINISH], [self.ROOT])
            else:
                super().execute(entries[index:end], stack)
            index = end

    def drain(self):
        for _ in range(100):
            if not self.scheduled:
                return
            self.scheduled.sort()
            self.day, event = self.scheduled.pop(0)
            self.call(event)
        raise AssertionError("Continuation failed to terminate")


class ScanReserveRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        effects = automation.generated_fixture().effects
        names = (SCAN, MERGE, FINISH, REFILL, TARGET, SETTLE,
                 "eu5ab_record_scan_candidate_location", "eu5ab_clear_scan_continuation",
                 "eu5ab_prepare_engine_candidate_queue", "eu5ab_clear_engine_candidate_queue",
                 "eu5ab_clear_location_candidate_state",
                 "eu5ab_clear_location_worker_state", "eu5ab_clear_backfill_worker_state",
                 "eu5ab_clear_backfill_scratch",
                 "eu5ab_scan_initial_tail", "eu5ab_scan_deferred_locations",
                 "eu5ab_clear_worker_screening", "eu5ab_clear_rgo_screening",
                 "eu5ab_batch_collect_cleanup",
                 "eu5ab_clear_location_winner", "eu5ab_clear_quote_production_snapshot",
                 "eu5ab_clear_quote_production_values",
                 "eu5ab_finish_regional_development_scan")
        cls.definitions = {}
        cls.definitions["test_country_counter_initializers"] = country_counter_initializers(effects)
        for name in names:
            block = automation._blocks_for_token(effects, "\n" + name + " = ")[0]
            cls.definitions[name] = parse(block)[0][2]
        for name, _, body in parse(automation.generated_fixture().events):
            if name in ("eu5ab_monthly.1", "eu5ab_monthly.2", "eu5ab_monthly.3"):
                cls.definitions[name] = next(v for k, _, v in body if k == "immediate")

    def vm(self, parallel=0):
        return ReserveVM(self.definitions, parallel)

    def test_reducer_deduplicates_buildings_phases_and_rgo_and_repeated_merge(self):
        vm = self.vm()
        vm.lists[vm.ROOT]["eu5ab_worker_pending_locations"] = ["a", "b"]
        for location in ("a", "b"):
            vm.execute([("eu5ab_run_location_worker", "=", "yes")], [location])
            vm.lists[location]["eu5ab_worker_phase_6_types"] = ["building_a"]
        vm.call(MERGE)
        self.assertEqual(vm.vars[vm.ROOT][RESERVE], 2)
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_q_staged"], 6)
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_q_rgo_staged"], 2)
        vm.call(MERGE)
        self.assertEqual(vm.vars[vm.ROOT][RESERVE], 2)

    def test_building_only_and_rgo_only_workers_each_supply_one_slot(self):
        for rgo_only in (False, True):
            vm = self.vm()
            vm.lists[vm.ROOT]["eu5ab_worker_pending_locations"] = ["a"]
            vm.execute([("eu5ab_run_location_worker", "=", "yes")], ["a"])
            if rgo_only:
                vm.vars["a"].pop("eu5ab_worker_staged")
                vm.lists["a"]["eu5ab_worker_phase_5_types"] = []
            else:
                vm.vars["a"].pop("eu5ab_worker_phase_7_rgo")
            vm.call(MERGE)
            self.assertEqual(vm.vars[vm.ROOT][RESERVE], 1)
    def test_rate_uses_unique_exhausted_locations_and_remaining_quota(self):
        vm = self.vm()
        country = vm.vars[vm.ROOT]
        country.update(eu5ab_monthly_build_quota=10, eu5ab_constructions_started_this_tick=2,
                       eu5ab_scan_candidate_reserve=8, eu5ab_diag_queue_state=4)
        vm.lists[vm.ROOT][PENDING] = ["b"]
        vm.call(SETTLE)
        self.assertAlmostEqual(country["eu5ab_scan_acceptance_rate"], 3 / 10)
        vm.call(TARGET)
        self.assertEqual(country["eu5ab_scan_candidate_target"], 27)
        self.assertEqual(vm.scheduled, [(24, "eu5ab_monthly.3")])
        # A later exhausted batch learns from the whole round, not repeated probes.
        country.update(eu5ab_scan_candidate_reserve=10, eu5ab_constructions_started_this_tick=3)
        country.pop("eu5ab_scan_refill_active")
        vm.call(SETTLE)
        self.assertEqual(country["eu5ab_scan_settled_locations"], 18)
        self.assertAlmostEqual(country["eu5ab_scan_acceptance_rate"], 4 / 20)
        vm.call(TARGET)
        self.assertEqual(country["eu5ab_scan_candidate_target"], 35)

    def test_failed_first_batch_resumes_only_unscanned_and_fills_quota(self):
        for parallel in (0, 1):
            with self.subTest(parallel=parallel):
                vm = self.vm(parallel)
                vm.day = 2
                locations = [f"site_{n}" for n in range(12)]
                for n, name in enumerate(locations):
                    vm.add_location(name)
                    vm.native[name]["score"] = 100 - n
                vm.lists[vm.ROOT]["eu5ab_scan_bucket_1_locations"] = locations
                vm.accepted = {"site_8", "site_9"}
                vm.call("eu5ab_monthly.1")
                vm.drain()
                country = vm.vars[vm.ROOT]
                self.assertEqual(country["eu5ab_constructions_started_this_tick"], 2)
                self.assertEqual(country["eu5ab_global_budget_remaining"], 980)
                # Day 22 fills the remaining reserve before the first batch.
                self.assertEqual(vm.batches[0], (23, ["site_0", "site_1", "site_2", "site_3"]))
                self.assertGreater(len(vm.batches), 1)
                dispatched = [name for _, name in vm.dispatched]
                self.assertEqual(len(dispatched), len(set(dispatched)))
                self.assertEqual(country["eu5ab_deep_score_attempts"], len(dispatched))
                self.assertLessEqual(max(Counter(day for day, _ in vm.dispatched).values()), 2)
                self.assertNotIn("eu5ab_scan_round_active", country)
                self.assertNotIn("eu5ab_scan_active", country)
                self.assertFalse(vm.lists[vm.ROOT][PENDING])

    def test_zero_success_terminates_at_original_budget(self):
        for parallel in (0, 1):
            vm = self.vm(parallel)
            country = vm.vars[vm.ROOT]
            country.update(eu5ab_deep_score_attempts=38, eu5ab_scan_candidate_reserve=2,
                           eu5ab_diag_queue_state=4)
            country.pop("eu5ab_scan_active")
            vm.lists[vm.ROOT][PENDING] = ["b", "i", "g"]
            vm.call(FINISH)
            vm.drain()
            self.assertEqual(country["eu5ab_deep_score_attempts"], 40)
            self.assertEqual(len(vm.dispatched), 2)
            self.assertNotIn("eu5ab_scan_round_active", country)
            self.assertGreaterEqual(country["eu5ab_scan_acceptance_rate"], 0.05)

    def test_low_daily_limit_stops_at_month_boundary_without_duplicates(self):
        for parallel in (0, 1):
            with self.subTest(parallel=parallel):
                vm = self.vm(parallel)
                vm.day = 2
                country = vm.vars[vm.ROOT]
                country.update(eu5ab_deep_score_budget=600,
                               eu5ab_scan_daily_task_limit=1)
                locations = [f'late_{n}' for n in range(35)]
                for n, name in enumerate(locations):
                    vm.add_location(name)
                    vm.native[name]['score'] = 100 - n
                vm.lists[vm.ROOT]['eu5ab_scan_bucket_1_locations'] = locations
                vm.accepted = {'late_30', 'late_31'}
                vm.call('eu5ab_monthly.1')
                vm.drain()
                dispatched = [name for _, name in vm.dispatched]
                self.assertEqual(len(dispatched), 10)
                self.assertTrue(all(day <= 31 for day, _ in vm.dispatched))
                self.assertEqual(len(dispatched), len(set(dispatched)))
                self.assertEqual(max(Counter(day for day, _ in vm.dispatched).values()), 1)
                # The accepted sites are beyond this month's remaining days.
                # They cannot consume next month's quota or scan allowance.
                self.assertEqual(country['eu5ab_constructions_started_this_tick'], 0)
                self.assertEqual(country['eu5ab_deep_score_attempts'], len(dispatched))
                self.assertNotIn('eu5ab_scan_round_active', country)
                self.assertNotIn('eu5ab_diag_scan_stalled', country)
                self.assertFalse(vm.lists[vm.ROOT][PENDING])

    def test_no_resume_or_learning_after_watchdog_or_full_quota(self):
        for watchdog, starts in ((True, 0), (False, 2)):
            vm = self.vm()
            country = vm.vars[vm.ROOT]
            country.update(eu5ab_diag_queue_state=5 if watchdog else 4,
                           eu5ab_constructions_started_this_tick=starts,
                           eu5ab_scan_candidate_reserve=100)
            vm.lists[vm.ROOT][PENDING] = ["b"]
            vm.call(FINISH)
            self.assertEqual(country["eu5ab_scan_acceptance_rate"], 0.5)
            self.assertEqual(vm.scheduled, [])
            self.assertNotIn("eu5ab_scan_round_active", country)

    def test_prunes_newly_invalid_sites_without_repeating_monthly_maintenance(self):
        vm = self.vm()
        country = vm.vars[vm.ROOT]
        country.pop("eu5ab_scan_active")
        country["eu5ab_scan_refill_active"] = 1
        vm.lists[vm.ROOT][PENDING] = list("abcdefghi")
        vm.owners["i"] = "foreign"
        vm.vars["foreign"], vm.lists["foreign"] = {}, {}
        vm.vars["b"]["eu5ab_wait_months"] = 7
        vm.call(REFILL)
        self.assertEqual([n for _, n in vm.dispatched], ["b"])
        self.assertEqual(vm.vars["a"]["eu5ab_build_cooldown"], 1)
        self.assertEqual(vm.vars["d"]["eu5ab_failure_cooldown"], 1)
        self.assertEqual(vm.vars["e"]["eu5ab_wait_months"], 7)
        self.assertFalse(vm.lists[vm.ROOT][PENDING])

    def test_commitments_and_backfill_snapshot_survive_refill_preparation(self):
        vm = self.vm()
        country = vm.vars[vm.ROOT]
        country.pop("eu5ab_scan_active")
        country.update(eu5ab_scan_candidate_reserve=2, eu5ab_constructions_started_this_tick=1)
        vm.lists[vm.ROOT][PENDING] = ["b"]
        vm.material_commitments = 5
        vm.call(FINISH)
        self.assertEqual(vm.material_commitments, 5)
        vm.day = 23
        vm.call("eu5ab_monthly.3")
        self.assertEqual(vm.material_commitments, 5)
        self.assertEqual(country["eu5ab_constructions_started_this_tick"], 1)
        self.assertTrue(country["eu5ab_scan_backfill_enabled"])
        self.assertEqual(vm.vars["b"]["eu5ab_backfill_dispatch_country"], vm.ROOT)

    def test_disable_or_stale_delayed_event_cannot_start_new_work(self):
        vm = self.vm()
        vm.vars[vm.ROOT].update(eu5ab_scan_refill_active=1, eu5ab_global_enabled=0)
        vm.lists[vm.ROOT][PENDING] = ["b"]
        vm.call("eu5ab_monthly.3")
        self.assertFalse(vm.dispatched)
        self.assertNotIn("eu5ab_scan_active", vm.vars[vm.ROOT])
        vm.vars[vm.ROOT]["eu5ab_global_enabled"] = 1
        vm.call("eu5ab_monthly.3")
        self.assertFalse(vm.dispatched)
        self.assertFalse(vm.scheduled)

    def test_finishing_a_round_does_not_release_a_deferred_month(self):
        vm = self.vm()
        country = vm.vars[vm.ROOT]
        country.pop("eu5ab_scan_active")
        country.update(eu5ab_scan_next_month_pending=1, eu5ab_q_active=1,
                       eu5ab_constructions_started_this_tick=2)
        # The ordinary monthly event must not reset a queue or active round.
        vm.call("eu5ab_monthly.1")
        self.assertEqual(country["eu5ab_constructions_started_this_tick"], 2)
        self.assertFalse(vm.scheduled)
        vm.call(FINISH)
        self.assertEqual(vm.scheduled, [])
        self.assertEqual(country['eu5ab_scan_next_month_pending'], 1)
        self.assertNotIn("eu5ab_q_active", country)

    def test_missing_variable_is_not_numeric_zero(self):
        vm = self.vm()
        country = vm.vars[vm.ROOT]
        country.pop(RESERVE, None)
        self.assertIsNone(vm.value("var:" + RESERVE, [vm.ROOT]))
        self.assertFalse(vm.test("var:" + RESERVE, "<", "62", [vm.ROOT]))
        self.assertFalse(vm.test("var:" + RESERVE, "=", "0", [vm.ROOT]))
        self.assertTrue(vm.test("eu5ab_scan_reserve_count", "<", "62", [vm.ROOT]))
        country[RESERVE] = 0
        self.assertTrue(vm.test("var:" + RESERVE, "=", "0", [vm.ROOT]))
        country.pop(RESERVE)
        with self.assertRaises(TypeError):
            vm.value(parse("value = 1 add = var:" + RESERVE), [vm.ROOT])

    def test_saved_586_of_600_scan_with_absent_reserve_completes(self):
        # Reduced state from the audited 1411.09--10 snapshots. Restore the
        # missing fields as missing, rather than silently seeding numeric zero.
        for parallel in (0, 1):
            vm = self.vm(parallel)
            country = vm.vars[vm.ROOT]
            country.update(eu5ab_scan_round_active=1, eu5ab_scan_refill_active=1,
                           eu5ab_deep_score_attempts=586, eu5ab_deep_score_budget=600,
                           eu5ab_scan_daily_task_limit=30, eu5ab_monthly_build_quota=98,
                           eu5ab_constructions_started_this_tick=67,
                           eu5ab_scan_candidate_target=62, eu5ab_scan_early_stop=1)
            for key in (RESERVE, "eu5ab_scan_active", "eu5ab_scan_settled_locations"):
                country.pop(key, None)
            locations = [f"saved_{n}" for n in range(20)]
            for location in locations:
                vm.add_location(location)
            vm.lists[vm.ROOT][PENDING] = locations
            vm.call("eu5ab_monthly.3")
            vm.drain()
            self.assertEqual(len(vm.dispatched), 14)
            self.assertEqual(country["eu5ab_deep_score_attempts"], 600)
            self.assertEqual(country["eu5ab_constructions_started_this_tick"], 67)
            self.assertEqual(country["eu5ab_global_budget_remaining"], 1000)
            self.assertNotIn("eu5ab_scan_round_active", country)
            self.assertNotIn("eu5ab_diag_scan_stalled", country)

    def test_empty_batch_does_not_train_acceptance_or_read_missing_reserve(self):
        vm = self.vm()
        country = vm.vars[vm.ROOT]
        country.update(eu5ab_monthly_build_quota=10, eu5ab_constructions_started_this_tick=0,
                       eu5ab_scan_acceptance_rate=0.25, eu5ab_scan_settled_locations=8)
        country.pop(RESERVE)
        vm.call(SETTLE)
        self.assertEqual(country["eu5ab_scan_settled_locations"], 8)
        self.assertEqual(country["eu5ab_scan_acceptance_rate"], 0.25)

    def test_saved_refill_batches_count_new_locations_in_acceptance_rate(self):
        for settled, started, quota, added in ((222, 35, 97, 1), (174, 31, 85, 8)):
            with self.subTest(settled=settled):
                vm = self.vm()
                country = vm.vars[vm.ROOT]
                country.update(eu5ab_scan_settled_locations=settled,
                               eu5ab_constructions_started_this_tick=started,
                               eu5ab_monthly_build_quota=quota, eu5ab_diag_queue_state=4)
                country.pop(RESERVE)
                for index in range(added):
                    vm.scopes["eu5ab_candidate_location"] = f"refill_{index}"
                    for _ in range(2):  # Repeated results cannot count twice.
                        vm.execute(vm.definitions["eu5ab_record_scan_candidate_location"], [vm.ROOT])
                self.assertEqual(country[RESERVE], added)
                self.assertEqual(len(vm.lists[vm.ROOT]["eu5ab_scan_candidate_locations"]), added)
                vm.call(SETTLE)
                self.assertEqual(country["eu5ab_scan_settled_locations"], settled + added)
                self.assertAlmostEqual(country["eu5ab_scan_acceptance_rate"],
                                       (started + 1) / (settled + added + 2))

    def test_stall_counter_restarts_after_progress_and_expires_on_sixth_check(self):
        vm = self.vm()
        country = vm.vars[vm.ROOT]
        check = "eu5ab_check_scan_refill_progress"
        vm.call(check)
        self.assertNotIn("eu5ab_scan_refill_stall_days", country)
        for day in range(1, REFILL_STALL_DAYS):
            vm.call(check)
            self.assertEqual(country["eu5ab_scan_refill_stall_days"], day)
            self.assertNotIn("eu5ab_diag_scan_stalled", country)
        country["eu5ab_deep_score_attempts"] += 1
        vm.call(check)
        self.assertNotIn("eu5ab_scan_refill_stall_days", country)
        for day in range(1, REFILL_STALL_DAYS):
            vm.call(check)
            self.assertEqual(country["eu5ab_scan_refill_stall_days"], day)
            self.assertIn("eu5ab_scan_round_active", country)
        vm.call(check)
        self.assertEqual(country["eu5ab_diag_scan_stalled"], 1)
        self.assertNotIn("eu5ab_scan_round_active", country)
        self.assertNotIn("eu5ab_scan_refill_stall_days", country)

    def test_workers_without_candidates_still_make_progress_and_terminate(self):
        for parallel in (0, 1):
            vm = self.vm(parallel)
            vm.worker_candidates = False
            country = vm.vars[vm.ROOT]
            country.pop("eu5ab_scan_active")
            country.pop(RESERVE)
            country.pop("eu5ab_constructions_started_this_tick")
            country.update(eu5ab_scan_refill_active=1, eu5ab_deep_score_attempts=0,
                           eu5ab_deep_score_budget=16, eu5ab_scan_daily_task_limit=1)
            locations = [f"empty_{n}" for n in range(20)]
            for location in locations:
                vm.add_location(location)
            vm.lists[vm.ROOT][PENDING] = locations
            vm.call("eu5ab_monthly.3")
            vm.drain()
            self.assertEqual(len(vm.dispatched), 9)
            self.assertTrue(all(day <= 31 for day, _ in vm.dispatched))
            self.assertNotIn("eu5ab_diag_scan_stalled", country)
            self.assertNotIn("eu5ab_scan_round_active", country)
            self.assertEqual(country["eu5ab_scan_acceptance_rate"], 0.5)

    def test_stalled_continuation_never_schedules_a_deferred_month(self):
        class BlockedDispatchVM(ReserveVM):
            def test(self, k, op, v, stack):
                if k == "eu5ab_scan_daily_attempt_count":
                    return False  # Inject a dispatch failure after eligibility.
                return super().test(k, op, v, stack)

        vm = BlockedDispatchVM(self.definitions)
        country = vm.vars[vm.ROOT]
        country.pop("eu5ab_scan_active")
        country.update(eu5ab_scan_refill_active=1, eu5ab_scan_next_month_pending=1,
                       eu5ab_deep_score_attempts=586, eu5ab_deep_score_budget=600,
                       eu5ab_monthly_build_quota=98, eu5ab_constructions_started_this_tick=67)
        vm.lists[vm.ROOT][PENDING] = ["b", "i"]
        vm.vars["b"]["eu5ab_build_cooldown"] = 2
        vm.lists[vm.ROOT]["eu5ab_active_project_locations"] = ["b"]
        vm.material_commitments = 5
        vm.call("eu5ab_monthly.3")
        for _ in range(REFILL_STALL_DAYS):
            vm.day, event = vm.scheduled.pop(0)
            self.assertEqual(event, "eu5ab_monthly.3")
            vm.call(event)
        self.assertFalse(vm.dispatched)
        self.assertEqual(country["eu5ab_diag_scan_stalled"], 1)
        for flag in ("eu5ab_scan_round_active", "eu5ab_scan_refill_active", "eu5ab_scan_active"):
            self.assertNotIn(flag, country)
        self.assertEqual(country['eu5ab_scan_next_month_pending'], 1)
        self.assertFalse(vm.lists[vm.ROOT][PENDING])
        self.assertEqual(vm.scheduled, [])
        self.assertEqual(country["eu5ab_constructions_started_this_tick"], 67)
        self.assertEqual(country["eu5ab_global_budget_remaining"], 1000)
        self.assertEqual(vm.lists[vm.ROOT]["eu5ab_active_project_locations"], ["b"])
        self.assertEqual(vm.vars["b"]["eu5ab_build_cooldown"], 2)
        self.assertEqual(vm.material_commitments, 0)

    def test_active_gui_queue_does_not_consume_scan_stall_allowance(self):
        vm = self.vm()
        country = vm.vars[vm.ROOT]
        country.update(eu5ab_scan_refill_active=1, eu5ab_q_active=1,
                       eu5ab_scan_refill_stall_days=REFILL_STALL_DAYS - 1)
        vm.call("eu5ab_monthly.3")
        self.assertEqual(country["eu5ab_scan_refill_stall_days"], REFILL_STALL_DAYS - 1)
        self.assertNotIn("eu5ab_diag_scan_stalled", country)


if __name__ == "__main__":
    unittest.main()
