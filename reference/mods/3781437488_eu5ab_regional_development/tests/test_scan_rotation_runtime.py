"""Execute F1 scheduling from generated scripts with injected native/worker results.

This verifies dispatch and state lifecycle, not EU5 economics or runtime speed.
"""

from copy import deepcopy
import unittest

from src.eu5autobuild import manual_decisions
from tests._governor_script_vm import parse
from tests import _generated as automation
from tests.test_scan_short_circuit_runtime import BUCKET, SCAN, ScanVM


RUN = "eu5ab_run_regional_development_policy"
RECOVER = "eu5ab_recover_runtime_after_load"
MARK_LOAD = "eu5ab_mark_interrupted_scan_on_load"
SCHEDULE_RESUME = "eu5ab_schedule_scan_resume_after_load"
FINISH = "eu5ab_finish_regional_development_scan"
START = "eu5ab_scan_start_bucket"
DAY = "eu5ab_scan_bucket_day"
INDEX = "eu5ab_scan_bucket_index"


class RotationVM(ScanVM):
    def __init__(self, definitions, parallel=0):
        super().__init__(definitions[SCAN], parallel=parallel)
        self.definitions.update(definitions)
        self.vars = {self.ROOT: {
            "eu5ab_global_parallel_location_scan": parallel,
            "eu5ab_global_daily_location_task_limit": 30,
            "eu5ab_global_max_additions_per_run": 0,
            "eu5ab_global_early_stop_when_candidates_sufficient": 1,
            "eu5ab_monthly_build_hard_cap": 0,  # Q=1 with no active projects.
            "eu5ab_scan_registry_schema_version": 1,
            "eu5ab_runtime_schema_version": 2,
            "eu5ab_global_enabled": 1,
        }}
        self.lists, self.owners, self.native = {self.ROOT: {}}, {}, {}
        for bucket in range(1, 21):
            name = f"location_{bucket}"
            self.add_location(name)
            self.vars[name].pop("eu5ab_bucket_need_score")
            self.lists[self.ROOT][BUCKET.format(bucket)] = [name]
        self.pending_candidates = 0
        self.candidates_per_worker = 1  # Unique locations, regardless of alternatives.
        self.scheduled, self.finalized = [], []
        self.day = 2
        self.call("eu5ab_ensure_template_coverage")

    def value(self, x, stack):
        if isinstance(x, str) and x.startswith('eu5ab_manual_') and x in self.definitions:
            return self.value(self.definitions[x], stack)
        if x in ("max_rgo_workers", "eu5ab_rgos_under_construction"):
            return 1
        return super().value(x, stack)

    def test(self, k, op, v, stack):
        if k == 'eu5ab_manual_month_current':
            return self.condition(self.definitions[k], stack) == (v == 'yes')
        if k == "always":
            return v == "yes"
        if k == 'is_human':
            return v == 'yes'
        if k == "current_month":
            return int(v) == 5
        if k == "has_variable_list":
            return bool(self.lists[stack[-1]].get(v))
        if k == "any_owned_location":
            return any(self.condition(v, stack + [location])
                       for location, owner in self.owners.items() if owner == stack[-1])
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
            if k == "clamp_variable":
                variables = self.vars[stack[-1]]
                variables[data["name"]] = max(float(data["min"]), min(
                    float(data["max"]), variables.get(data["name"], 0)))
            elif k == "trigger_event_silently" and "id" in data:
                self.scheduled.append((self.day + int(data["days"]), data["id"]))
            elif k in (
                "eu5ab_pl_new_round", "eu5ab_pl_new_epoch",
                "eu5ab_prepare_engine_candidate_queue", "eu5ab_clear_engine_candidate_queue",
                "eu5ab_reset_committed_construction_demand", "eu5ab_hydrate_final_building_diagnostics",
                "eu5ab_reset_policy_budgets_if_needed", "eu5ab_clear_location_worker_state",
                "eu5ab_ensure_build_pending",
                "eu5ab_clear_scan_market_cache", "eu5ab_clear_active_candidate_catalogs",
                "eu5ab_migrate_rgo_pending_registry", "eu5ab_batch_rgo_migrate_attempts",
                "eu5ab_clear_winner_batch",
                "eu5ab_clear_queue_bridge",
                "eu5ab_pf_rebuild_goods_index", "eu5ab_pf_resume_maintenance",
            ):
                pass  # Outside the scheduler; no native construction is simulated.
            elif k == "eu5ab_start_engine_candidate_queue":
                self.finalized.append(self.day)
                self.execute(self.definitions["eu5ab_clear_scan_continuation"], stack)
            else:
                if k in ("eu5ab_request_building_capacity", "eu5ab_run_location_worker", "trigger_event_silently"):
                    # Inject a GUI/worker result at the request boundary.
                    self.pending_candidates += self.candidates_per_worker
                elif k == "eu5ab_merge_location_worker_results":
                    country = self.vars[stack[-1]]
                    country["eu5ab_scan_candidate_reserve"] = (
                        country.get("eu5ab_scan_candidate_reserve", 0) + self.pending_candidates
                    )
                    self.pending_candidates = 0
                    self.lists[stack[-1]]["eu5ab_worker_pending_locations"] = []
                super().execute(entries[index:end], stack)
            index = end

    def month(self):
        # Each invocation represents a fresh monthly pulse, not another scan
        # in the same calendar month. Rotation remains independent of the stamp.
        self.vars[self.ROOT].pop('eu5ab_scan_month', None)
        self.vars[self.ROOT].pop('eu5ab_scan_dispatch_day', None)
        self.day = 2
        self.calls, self.score_calls, self.sort_calls = [], [], 0
        self.scheduled = [(2, "eu5ab_monthly.1")]
        while self.scheduled:
            self.day, event = self.scheduled.pop(0)
            if self.day > 23:
                raise AssertionError(f"Scan continued past day 23: {self.day}")
            self.call(event)

    def workers(self):
        return [row[1] for row in self.calls if row[0] != "eu5ab_merge_location_worker_results"]


class ScanRotationRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.definitions = {}
        for symbol in (RUN, SCAN, FINISH, RECOVER, MARK_LOAD, SCHEDULE_RESUME,
                       "eu5ab_manual_expire",
                       "eu5ab_clear_location_candidate_state", "eu5ab_scan_initial_tail",
                       "eu5ab_scan_deferred_locations"):
            text = automation._blocks_for_token(
                automation.generated_fixture().effects, "\n" + symbol + " = "
            )[0]
            cls.definitions[symbol] = parse(text)[0][2]
        cls.definitions.update({k: v for k, _, v in parse(manual_decisions.render_triggers())})
        cls.definitions.update({k: v for k, _, v in parse(automation.generated_fixture().values)
                                if k.startswith('eu5ab_manual_')})
        for symbol, _, body in parse(automation.generated_fixture().events):
            if symbol in ("eu5ab_monthly.1", "eu5ab_monthly.2", "eu5ab_monthly.4"):
                cls.definitions[symbol] = next(v for k, _, v in body if k == "immediate")

    def test_coverage_stays_constant_during_scan_and_next_month(self):
        for parallel, early_stop in ((0, 1), (1, 0)):
            with self.subTest(parallel=parallel, early_stop=early_stop):
                vm = RotationVM(self.definitions, parallel)
                country = vm.vars[vm.ROOT]
                country["eu5ab_global_early_stop_when_candidates_sufficient"] = early_stop
                for _ in range(2):
                    country.pop("eu5ab_scan_month", None)
                    country.pop("eu5ab_scan_dispatch_day", None)
                    vm.scheduled = [(2, "eu5ab_monthly.1")]
                    while vm.scheduled:
                        vm.day, event = vm.scheduled.pop(0)
                        vm.call(event)
                        self.assertEqual(country["eu5ab_diag_covered_locations"], 20)

    def test_every_start_visits_all_buckets_once_and_finishes_on_day_23(self):
        for parallel in (0, 1):
            for start in range(1, 21):
                with self.subTest(parallel=parallel, start=start):
                    vm = RotationVM(self.definitions, parallel)
                    country = vm.vars[vm.ROOT]
                    country.update({START: start - 1, "eu5ab_monthly_build_hard_cap": 599,
                                    "eu5ab_global_early_stop_when_candidates_sufficient": 0})
                    for name in vm.native:
                        vm.vars[name]["eu5ab_recent_build_penalty"] = 2
                    vm.month()
                    order = list(range(start, 21)) + list(range(1, start))
                    self.assertEqual(vm.workers(), [f"location_{n}" for n in order])
                    self.assertEqual(country[START], start)
                    self.assertEqual(country["eu5ab_diag_covered_locations"], 20)
                    self.assertEqual(country["eu5ab_diag_deep_scored"], 20)
                    self.assertEqual(vm.finalized, [23])
                    for name in (DAY, INDEX, "eu5ab_scan_active"):
                        self.assertNotIn(name, country)
                    for name in vm.native:
                        self.assertEqual(vm.vars[name]["eu5ab_recent_build_penalty"], 1)

    def test_low_quota_early_stop_first_opportunity_reaches_every_bucket(self):
        for parallel in (0, 1):
            vm = RotationVM(self.definitions, parallel)
            # Multiple alternatives at one location supply only one reserve slot.
            for run in range(1, 22):
                vm.month()
                expected = f"location_{(run - 1) % 20 + 1}"
                second = f"location_{run % 20 + 1}"
                self.assertEqual(vm.workers(), [expected, second])
                country = vm.vars[vm.ROOT]
                self.assertEqual(country["eu5ab_scan_candidate_reserve"], 2)
                self.assertEqual(country["eu5ab_scan_candidate_target"], 2)
                self.assertEqual(country["eu5ab_deep_score_budget"], 20)
                self.assertEqual(country["eu5ab_diag_preliminary_passed"], 20)
                self.assertEqual(country["eu5ab_diag_deep_scored"], 2)
                self.assertEqual(len(vm.score_calls), 2)
                self.assertEqual(vm.sort_calls, 4)
                self.assertNotIn("eu5ab_wait_months", vm.vars[expected])
            self.assertEqual(vm.finalized, [23] * 21)

    def test_quota_zero_does_not_initialize_or_advance_start(self):
        for previous in (None, 7, 20):
            vm = RotationVM(self.definitions)
            if previous is not None:
                vm.vars[vm.ROOT][START] = previous
            vm.add_location("busy")
            vm.vars["busy"]['eu5ab_active_rgo_construction'] = 1
            vm.execute([("eu5ab_sync_location_template_coverage", "=", "yes")], ["busy"])
            vm.lists[vm.ROOT]["eu5ab_active_project_locations"] = ["busy"]
            vm.month()
            self.assertEqual(vm.vars[vm.ROOT].get(START), previous)
            self.assertEqual(vm.workers(), [])
            self.assertEqual(vm.finalized, [])
            self.assertNotIn("eu5ab_scan_active", vm.vars[vm.ROOT])
            self.assertEqual(vm.vars[vm.ROOT]["eu5ab_diag_covered_locations"], 21)

    def test_rgo_capacity_growth_and_unknown_queue_keep_confirmed_slot(self):
        for queue in (1, -1, 0):
            with self.subTest(queue=queue):
                vm = RotationVM(self.definitions)
                vm.add_location('busy')
                vm.vars['busy']['eu5ab_active_rgo_construction'] = 1
                vm.lists[vm.ROOT]['eu5ab_active_project_locations'] = ['busy']
                value = vm.value
                def inputs(x, stack):
                    if x == 'max_rgo_workers': return 13.62110
                    if x == 'eu5ab_rgos_under_construction': return queue
                    if x == 'eu5ab_manual_value_monthly_build_hard_cap':
                        return vm.vars[vm.ROOT]['eu5ab_monthly_build_hard_cap']
                    return value(x, stack)

                vm.value = inputs
                # Execute the actual monthly index reconciliation through its
                # quota debit, without unrelated scheduling/manual controls.
                entries = self.definitions[RUN]
                start = next(i for i, (k, _, v) in enumerate(entries)
                             if k == 'save_scope_as' and v == 'eu5ab_active_project_country')
                end = next(i for i, (k, _, v) in enumerate(entries) if k == 'change_variable'
                           and dict((a, c) for a, _, c in v).get('subtract') == 'var:eu5ab_diag_active_mod_projects')
                vm.vars[vm.ROOT].update(eu5ab_monthly_build_hard_cap=599, eu5ab_diag_active_mod_projects=0)
                vm.execute(entries[start:end + 1], [vm.ROOT])
                self.assertEqual(vm.vars[vm.ROOT]['eu5ab_diag_active_mod_projects'], int(queue != 0))
                self.assertEqual(vm.vars[vm.ROOT]['eu5ab_monthly_build_quota'], 600 - int(queue != 0))
                self.assertEqual('eu5ab_active_rgo_construction' in vm.vars['busy'], queue != 0)

    def test_interrupted_save_recovery_preserves_progress_and_country_independence(self):
        vm = RotationVM(self.definitions)
        country = vm.vars[vm.ROOT]
        country.update({START: 18, "eu5ab_global_budget_remaining": 500,
                        "eu5ab_monthly_build_hard_cap": 599})
        vm.call("eu5ab_monthly.1")
        self.assertEqual(country[START], 19)
        self.assertEqual(country[DAY], 2)
        saved = deepcopy((vm.vars, vm.lists))
        restored = RotationVM(self.definitions)
        restored.vars, restored.lists = saved
        before = deepcopy((restored.vars, restored.lists))
        restored.call(RECOVER)
        before[0][restored.ROOT]['eu5ab_bridge_rebuild'] = True
        self.assertEqual((restored.vars, restored.lists), before)
        self.assertEqual(restored.vars[restored.ROOT][START], 19)
        self.assertEqual(restored.vars[restored.ROOT][DAY], 2)
        self.assertEqual(restored.vars[restored.ROOT]["eu5ab_global_budget_remaining"], 500)
        restored.day = 3
        restored.call("eu5ab_monthly.1")
        self.assertEqual(restored.workers(), ["location_20"])
        self.assertEqual(restored.vars[restored.ROOT][DAY], 3)
        other = RotationVM(self.definitions)
        other.month()
        self.assertEqual(other.workers(), ["location_1", "location_2"])
        self.assertEqual(country[START], 19)

    def test_interrupted_load_drains_saved_callback_then_continues_once(self):
        vm = RotationVM(self.definitions)
        country = vm.vars[vm.ROOT]
        country.update({START: 18, "eu5ab_global_enabled": 1,
                        "eu5ab_global_budget_remaining": 500,
                        "eu5ab_monthly_build_hard_cap": 599})
        vm.call("eu5ab_monthly.1")
        self.assertEqual(country[START], 19)
        self.assertEqual(vm.scheduled, [(3, "eu5ab_monthly.1")])

        restored = RotationVM(self.definitions)
        restored.vars, restored.lists, restored.scheduled = deepcopy(
            (vm.vars, vm.lists, vm.scheduled)
        )
        country = restored.vars[restored.ROOT]
        country['eu5ab_scan_next_month_pending'] = 1
        for effect in (MARK_LOAD, RECOVER, SCHEDULE_RESUME):
            restored.call(effect)
        self.assertIn("eu5ab_scan_resume_after_load", country)
        self.assertIn("eu5ab_scan_active", country)
        self.assertIn("eu5ab_scan_next_month_pending", country)
        self.assertEqual(country[START], 19)
        self.assertEqual(country["eu5ab_global_budget_remaining"], 500)
        self.assertEqual(restored.scheduled, [
            (3, "eu5ab_monthly.1"), (5, "eu5ab_monthly.4"),
        ])

        restored.day, event = restored.scheduled.pop(0)
        restored.call(event)  # Saved callback must not start an extra scan.
        self.assertEqual(country[START], 19)
        self.assertEqual(restored.workers(), [])
        self.assertEqual(restored.scheduled, [(5, "eu5ab_monthly.4")])

        restored.day, event = restored.scheduled.pop(0)
        restored.call(event)
        self.assertNotIn("eu5ab_scan_resume_after_load", country)
        self.assertEqual(restored.scheduled, [(6, "eu5ab_monthly.1")])
        restored.call(event)  # Repeated load can queue a duplicate resume event.
        self.assertEqual(restored.scheduled, [(6, "eu5ab_monthly.1")])
        restored.day, event = restored.scheduled.pop(0)
        restored.call(event)
        self.assertEqual(country[START], 19)
        self.assertEqual(country[DAY], 3)
        self.assertEqual(restored.workers(), ["location_20"])
        self.assertEqual(country["eu5ab_global_budget_remaining"], 500)
        self.assertIn("eu5ab_scan_active", country)

    def test_deep_budget_and_daily_limit_still_bound_rotated_dispatch(self):
        for parallel in (0, 1):
            vm = RotationVM(self.definitions, parallel)
            vm.vars[vm.ROOT].update({START: 19, "eu5ab_monthly_build_hard_cap": 1,
                                    "eu5ab_global_early_stop_when_candidates_sufficient": 0})
            for bucket in range(1, 21):
                second = f"second_{bucket}"
                vm.add_location(second)
                vm.vars[second].pop("eu5ab_bucket_need_score")
                vm.lists[vm.ROOT][BUCKET.format(bucket)].append(second)
            vm.month()
            country = vm.vars[vm.ROOT]
            self.assertEqual(country["eu5ab_deep_score_attempts"], 20)
            self.assertEqual(country["eu5ab_diag_preliminary_passed"], 40)
            # Q=2 still yields budget20 and one worker per day, even after rotation.
            self.assertEqual(len(vm.workers()), 20)
            self.assertEqual(len(set(vm.workers())), 20)

    def test_daily_pacing_does_not_reduce_round_search_budget(self):
        for daily_limit in (1, 10, 20, 30):
            with self.subTest(daily_limit=daily_limit):
                vm = RotationVM(self.definitions)
                country = vm.vars[vm.ROOT]
                country.update(eu5ab_global_daily_location_task_limit=daily_limit,
                               eu5ab_monthly_build_hard_cap=400)
                vm.call(RUN)
                self.assertEqual(country['eu5ab_scan_daily_task_limit'], daily_limit)
                self.assertEqual(country['eu5ab_deep_score_budget'], 600)

    def test_day_22_scans_deferred_locations_without_exceeding_600(self):
        for parallel in (0, 1):
            vm = RotationVM(self.definitions, parallel)
            country = vm.vars[vm.ROOT]
            country.update(eu5ab_monthly_build_hard_cap=599,
                           eu5ab_global_early_stop_when_candidates_sufficient=0)
            for bucket in range(1, 21):
                for index in range(29):
                    name = f'extra_{bucket}_{index}'
                    vm.add_location(name)
                    vm.vars[name]['eu5ab_recent_build_penalty'] = 2
                    vm.lists[vm.ROOT][BUCKET.format(bucket)].append(name)
            vm.scheduled = [(2, 'eu5ab_monthly.1')]
            totals = {}
            while vm.scheduled:
                vm.day, event = vm.scheduled.pop(0)
                vm.call(event)
                totals[vm.day] = country['eu5ab_deep_score_attempts']
                self.assertLessEqual(totals[vm.day], 600)
            self.assertEqual((totals[21], totals[22]), (580, 600))
            self.assertEqual(len(set(vm.workers())), 600)
            self.assertEqual(vm.finalized, [23])
            for name in vm.native:
                if name.startswith('extra_'):
                    self.assertEqual(vm.vars[name]['eu5ab_recent_build_penalty'], 1)

    def test_legacy_day_22_finalizer_runs_tail_once_then_waits_for_23(self):
        vm = RotationVM(self.definitions)
        vm.call(RUN)
        country = vm.vars[vm.ROOT]
        country.update(eu5ab_scan_finalizing=1, eu5ab_deep_score_attempts=599,
                       eu5ab_deep_score_budget=600, eu5ab_scan_early_stop=0)
        vm.lists[vm.ROOT]['eu5ab_scan_unscanned_locations'] = ['location_1']
        vm.day = 22
        vm.call('eu5ab_monthly.2')
        vm.call('eu5ab_monthly.2')
        self.assertEqual(vm.workers(), ['location_1'])
        self.assertEqual(country['eu5ab_deep_score_attempts'], 600)
        self.assertEqual(vm.finalized, [])
        while vm.scheduled:
            vm.day, event = vm.scheduled.pop(0)
            vm.call(event)
        self.assertEqual(vm.finalized, [23])

    def test_date_records_actual_scan_day_and_survives_later_settlement(self):
        vm = RotationVM(self.definitions)
        vm.call(RUN)
        vm.day = 27
        vm.call(SCAN)
        country = vm.vars[vm.ROOT]
        date = tuple(country['eu5ab_diag_last_run_' + part] for part in ('year', 'month', 'day'))
        self.assertEqual(date, (1410, 5, 27))
        vm.day = 29
        vm.call(FINISH)
        vm.call(RECOVER)
        self.assertEqual(tuple(country['eu5ab_diag_last_run_' + part]
                               for part in ('year', 'month', 'day')), date)


if __name__ == "__main__":
    unittest.main()
