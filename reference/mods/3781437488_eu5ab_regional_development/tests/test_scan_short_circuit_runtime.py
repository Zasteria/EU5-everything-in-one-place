"""Execute the generated F2 scan with injected native and worker results.

This is not an EU5 emulator or a performance benchmark. Native eligibility,
score values and worker/reducer bodies are injected; actual generated scan
branches, scopes, arithmetic, lists and dispatch order run in the strict VM.
"""

from copy import deepcopy
import unittest

from src.eu5autobuild.candidate_backfill import render_effects
from src.eu5autobuild import annual_budget, scan_reserve, building_capacity, monthly_schedule, save_resume, production_cohorts, template_coverage
from tests._governor_script_vm import GovernorScriptVM, parse
from tests import _generated as automation


SCAN = "eu5ab_scan_regional_development_bucket"
STOP = "eu5ab_bucket_dispatch_stopped"
BUCKET = "eu5ab_scan_bucket_{}_locations"
PREPARE_BACKFILL = dict((k, v) for k, _, v in parse(render_effects(
    planning_default=3, profit_default=10,
)))["eu5ab_prepare_backfill_dispatch"]


class ScanVM(GovernorScriptVM):
    def __init__(self, definition, bucket=1, parallel=0):
        # Only the shared interpreter's generic state is needed, not its planner.
        self.definitions = {SCAN: definition}
        self.definitions.update({k: v for k, _, v in parse(annual_budget.render_scan_date())})
        self.definitions.update({k: v for k, _, v in parse(building_capacity.render_effects())})
        self.definitions.update({k: v for k, _, v in parse(scan_reserve.render_effects())})
        self.definitions.update({k: v for k, _, v in parse(scan_reserve.render_watchdog())})
        self.definitions.update({k: v for k, _, v in parse(monthly_schedule.render_effects())})
        self.definitions.update({k: v for k, _, v in parse(template_coverage.render_effects())})
        self.definitions.update({k: v for k, _, v in parse(production_cohorts.render_maintenance_effects())})
        self.definitions['eu5ab_settle_saved_approvals'] = dict(
            (k, v) for k, _, v in parse(save_resume.render_effects()))['eu5ab_settle_saved_approvals']
        self.calendar_triggers = {k: v for k, _, v in parse(monthly_schedule.render_triggers())}
        self.value_definitions = {k: v for k, _, v in parse(scan_reserve.render_values())}
        self.local, self.scopes = {}, {}
        self.operations = 0
        self.vars = {self.ROOT: dict(
            eu5ab_scan_bucket_day=bucket, eu5ab_scan_parallel=parallel,
            eu5ab_deep_score_budget=100, eu5ab_deep_score_attempts=0,
            eu5ab_scan_daily_task_limit=3, eu5ab_scan_early_stop=1,
            eu5ab_scan_candidate_reserve=0, eu5ab_scan_candidate_target=10,
            eu5ab_diag_covered_locations=3, eu5ab_diag_preliminary_passed=5,
            eu5ab_diag_deep_scored=7,
        )}
        self.lists = {self.ROOT: {}}
        self.owners = {}
        self.native = {}
        self.calls, self.score_calls = [], []
        self.sort_calls = 0
        self.merge_gain = 0
        for name in "abcdefghi":
            self.add_location(name)
        self.native["a"].update(score=10, emergency=True)
        self.vars["a"].update(eu5ab_build_cooldown=1, eu5ab_wait_months=5,
                              eu5ab_recent_build_penalty=2)
        self.native["b"]["score"] = 100
        self.vars["c"]["eu5ab_build_cooldown"] = 2
        self.native["d"].update(score=30, emergency=True)
        self.vars["d"]["eu5ab_failure_cooldown"] = 1
        self.native["e"]["paused"] = True
        self.vars["e"].update(eu5ab_wait_months=7, eu5ab_recent_build_penalty=1)
        self.native["f"]["construction"] = 1
        self.vars["g"].pop("eu5ab_policy_id")
        self.vars["h"]["eu5ab_failure_cooldown"] = 2
        self.native["i"]["score"] = 100  # Equal-score ordering must not change.
        self.lists[self.ROOT][BUCKET.format(bucket)] = list("abcdefghi")

    def add_location(self, name):
        self.vars[name] = {"eu5ab_policy_id": 1, "eu5ab_bucket_need_score": 999}
        self.lists[name] = {}
        self.owners[name] = self.ROOT
        self.native[name] = dict(score=0, paused=False, emergency=False, construction=0)

    def value(self, x, stack):
        if x == 'eu5ab_pl_today':
            return (self.value('current_year', stack) * 372
                    + self.value('current_month', stack) * 31 + self.value('current_day', stack))
        if x == 'current_month':
            return 5 + (getattr(self, 'day', 2) - 1) // 31
        if x == 'current_day':
            return (getattr(self, 'day', 2) - 1) % 31 + 1
        if isinstance(x, str) and x in self.value_definitions:
            # Execute the generated zero-default getter, including its guard.
            arithmetic = []
            for k, op, v in self.value_definitions[x]:
                if k == "if":
                    limit = next(body for key, _, body in v if key == "limit")
                    if self.condition(limit, stack):
                        arithmetic.extend(e for e in v if e[0] != "limit")
                else:
                    arithmetic.append((k, op, v))
            return super().value(arithmetic, stack)
        if x == "num_civil_constructions":
            return self.native[stack[-1]]["construction"]
        if x == "eu5ab_location_need_score":
            location = stack[-1]
            variables = self.vars[location]
            waiting = variables.get("eu5ab_wait_months", 0)
            penalty = variables.get("eu5ab_recent_build_penalty", 0)
            self.score_calls.append((location, waiting, penalty))
            return self.native[location]["score"] + waiting - penalty
        # Missing variable scopes remain None. In particular, a raw comparison
        # cannot turn an absent reserve into zero (confirmed by real game logs).
        return super().value(x, stack)

    def test(self, k, op, v, stack):
        if k in self.calendar_triggers:
            return self.condition(self.calendar_triggers[k], stack) == (v == 'yes')
        if k == 'eu5ab_location_has_parallel_room':
            return (self.native[stack[-1]]['construction'] < self.native[stack[-1]].get('capacity', 1)) == (v == 'yes')
        data = dict((a, c) for a, _, c in v) if isinstance(v, list) else {}
        if k == "owner" and isinstance(v, list):
            owner = self.owners.get(stack[-1])
            return owner is not None and self.condition(v, stack + [owner])
        if k == "any_in_list":
            body = [e for e in v if e[0] != "variable"]
            return any(self.condition(body, stack + [location])
                       for location in self.lists[stack[-1]].get(data["variable"], []))
        if k == "is_target_in_variable_list":
            return self.value(data["target"], stack) in self.lists[stack[-1]].get(data["name"], [])
        if k == "has_variable_list":
            return bool(self.lists[stack[-1]].get(v))
        if k == "eu5ab_location_template_not_paused":
            return (not self.native[stack[-1]]["paused"]) == (v == "yes")
        if k == "eu5ab_food_emergency_enabled":
            return self.native[stack[-1]]["emergency"] == (v == "yes")
        return super().test(k, op, v, stack)

    def execute(self, entries, stack):
        index = 0
        while index < len(entries):
            k, _, v = entries[index]
            end = index + 1
            if k == "if":
                while end < len(entries) and entries[end][0] in ("else_if", "else"):
                    end += 1
            if k == "owner":
                self.execute(v, stack + [self.owners[stack[-1]]])
            elif k in ("eu5ab_refresh_rgo_pending", "eu5ab_refresh_build_pending", "eu5ab_ensure_build_pending",
                       "eu5ab_clear_native_recipes", "eu5ab_clear_parallel_capacity",
                       "eu5ab_apply_queue_cooldowns"):
                pass  # Ledger economics are covered by test_rgo_pending_runtime.
            elif k == "remove_list_variable":
                data = dict((a, c) for a, _, c in v)
                pool = self.lists[stack[-1]].get(data["name"], [])
                target = self.value(data["target"], stack)
                self.lists[stack[-1]][data["name"]] = [n for n in pool if n != target]
            elif k == "eu5ab_prepare_backfill_dispatch":
                self.execute(PREPARE_BACKFILL, stack)
            elif k in ("eu5ab_request_building_capacity", "eu5ab_run_location_worker", "trigger_event_silently"):
                if k == "trigger_event_silently":
                    if v != [("on_action", "=", "eu5ab_parallel_location_scan_on_action")]:
                        raise AssertionError(v)
                location = stack[-1]
                # This scheduler harness observes the request boundary. Native
                # capture and one-shot worker delivery are tested separately.
                self.calls.append((k, location, self.vars[location].get("eu5ab_cached_location_need_score", 0)))
            elif k == "eu5ab_merge_location_worker_results":
                self.calls.append((k, stack[-1]))
                if self.merge_gain:
                    variables = self.vars[stack[-1]]
                    variables["eu5ab_scan_candidate_reserve"] = variables.get("eu5ab_scan_candidate_reserve", 0) + self.merge_gain
            else:
                if k == "ordered_in_list":
                    self.sort_calls += 1
                super().execute(entries[index:end], stack)
                # Explicit numeric zero and an absent variable are different.
                # Save recovery cases delete counters explicitly in their tests.
            index = end


class ScanShortCircuitRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        current = automation._blocks_for_token(
            automation.generated_fixture().effects, "\n" + SCAN + " = "
        )[0]
        cls.current = parse(current)[0][2]

    def vm(self, bucket=1, parallel=0):
        return ScanVM(self.current, bucket, parallel)

    def assert_scanned(self, vm, *, skipped=False):
        vm.call(SCAN)
        self.assertNotIn(STOP, vm.vars[vm.ROOT])
        for variables in vm.vars.values():
            self.assertNotIn("eu5ab_bucket_need_score", variables)
        if skipped:
            self.assertEqual(vm.score_calls, [])
            self.assertEqual(vm.sort_calls, 0)

    def test_all_buckets_at_global_stop_boundaries_in_both_modes(self):
        scenarios = (
            ({"eu5ab_scan_candidate_reserve": 9}, False),
            ({"eu5ab_scan_candidate_reserve": 10}, True),
            ({"eu5ab_scan_candidate_reserve": 11}, True),
            ({"eu5ab_deep_score_attempts": 99}, False),
            ({"eu5ab_deep_score_attempts": 100}, True),
            ({"eu5ab_deep_score_attempts": 101}, True),
            ({"eu5ab_scan_early_stop": 0, "eu5ab_scan_candidate_reserve": 11}, False),
            ({"eu5ab_scan_early_stop": 0, "eu5ab_deep_score_attempts": 100}, True),
        )
        for bucket in range(1, 21):
            for parallel in (0, 1):
                for overrides, stopped in scenarios:
                    with self.subTest(bucket=bucket, parallel=parallel, state=overrides):
                        vm = self.vm(bucket, parallel)
                        vm.vars[vm.ROOT].update(overrides)
                        self.assert_scanned(vm, skipped=stopped)
                        if not stopped:
                            self.assertEqual(len(vm.score_calls), 4)
                            self.assertEqual(vm.sort_calls, 2)
                        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_diag_covered_locations"], 3)
                        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_diag_preliminary_passed"], 9)
                        if stopped:
                            self.assertEqual(vm.vars["a"]["eu5ab_wait_months"], 6)
                            self.assertEqual(vm.vars["a"]["eu5ab_recent_build_penalty"], 1)
                            self.assertNotIn("eu5ab_build_cooldown", vm.vars["a"])
                            self.assertEqual(vm.vars["c"]["eu5ab_build_cooldown"], 1)
                            self.assertNotIn("eu5ab_failure_cooldown", vm.vars["d"])
                            self.assertEqual(vm.vars["e"]["eu5ab_wait_months"], 7)

    def test_active_partition_order_scores_and_daily_limit_are_unchanged(self):
        for parallel in (0, 1):
            vm = self.vm(parallel=parallel)
            self.assert_scanned(vm)
            workers = [row for row in vm.calls if row[0] != "eu5ab_merge_location_worker_results"]
            self.assertEqual([(row[1], row[2]) for row in workers], [("d", 31), ("a", 15), ("b", 101)])
            self.assertEqual(vm.lists[vm.ROOT]["eu5ab_worker_pending_locations"], ["d", "a", "b"])
            self.assertEqual(vm.vars["i"]["eu5ab_wait_months"], 1)

    def test_global_budget_reached_during_dispatch_preserves_last_worker(self):
        for parallel in (0, 1):
            vm = self.vm(parallel=parallel)
            vm.vars[vm.ROOT]["eu5ab_deep_score_attempts"] = 99
            self.assert_scanned(vm)
            self.assertEqual(vm.lists[vm.ROOT]["eu5ab_worker_pending_locations"], ["d"])
            self.assertEqual(vm.vars[vm.ROOT]["eu5ab_deep_score_attempts"], 100)

    def test_reserve_merge_and_later_bucket_stop_preserve_reducer(self):
        vm = self.vm()
        vm.vars[vm.ROOT]["eu5ab_scan_candidate_reserve"] = 9
        vm.merge_gain = 2
        self.assert_scanned(vm)
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_scan_candidate_reserve"], 11)
        vm.vars[vm.ROOT]["eu5ab_scan_bucket_day"] = 20
        vm.lists[vm.ROOT][BUCKET.format(20)] = vm.lists[vm.ROOT][BUCKET.format(1)].copy()
        vm.score_calls, vm.calls, vm.sort_calls = [], [], 0
        self.assert_scanned(vm, skipped=True)
        self.assertEqual(vm.calls, [("eu5ab_merge_location_worker_results", vm.ROOT)])
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_scan_candidate_reserve"], 13)

    def test_daily_quota_resets_on_next_call_and_does_not_latch_stop(self):
        vm = self.vm()
        self.assert_scanned(vm)
        vm.score_calls, vm.calls, vm.sort_calls = [], [], 0
        self.assert_scanned(vm)
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_deep_score_attempts"], 6)
        self.assertEqual(len(vm.calls), 4)  # Three workers, then the reducer.

    def test_new_scan_ignores_any_stale_scratch_stop(self):
        vm = self.vm()
        vm.vars[vm.ROOT]["eu5ab_scan_candidate_reserve"] = 10
        self.assert_scanned(vm, skipped=True)
        vm.vars[vm.ROOT]["eu5ab_scan_candidate_reserve"] = 0
        vm.score_calls, vm.calls, vm.sort_calls = [], [], 0
        vm.vars[vm.ROOT][STOP] = 1  # Simulated stale/load state, cleared on entry.
        self.assert_scanned(vm)
        self.assertTrue(vm.score_calls)

    def test_foreign_or_unowned_bucket_member_uses_original_dispatch_path(self):
        for owner in ("foreign", None):
            for parallel in (0, 1):
                vm = self.vm(parallel=parallel)
                vm.vars["foreign"] = deepcopy(vm.vars[vm.ROOT])
                vm.vars["foreign"].update(eu5ab_daily_deep_score_budget=3,
                                          eu5ab_daily_deep_score_attempts=0)
                vm.lists["foreign"] = {}
                vm.owners["i"] = owner
                vm.vars[vm.ROOT]["eu5ab_scan_candidate_reserve"] = 10
                with self.subTest(owner=owner, parallel=parallel):
                    self.assert_scanned(vm)
                    workers = [row for row in vm.calls if row[0] != "eu5ab_merge_location_worker_results"]
                    self.assertEqual([row[1] for row in workers], ["i"] if owner else [])

    def test_empty_bucket_and_zero_daily_quota_keep_cleanup_and_merge(self):
        for empty in (False, True):
            for stopped in (False, True):
                vm = self.vm(bucket=20)
                vm.vars[vm.ROOT]["eu5ab_scan_daily_task_limit"] = 0
                if stopped:
                    vm.vars[vm.ROOT]["eu5ab_scan_candidate_reserve"] = 10
                if empty:
                    vm.lists[vm.ROOT][BUCKET.format(20)] = []
                    for name in vm.native:
                        vm.vars[name].pop("eu5ab_bucket_need_score")
                self.assert_scanned(vm, skipped=stopped)
                self.assertEqual(vm.calls, [("eu5ab_merge_location_worker_results", vm.ROOT)])


if __name__ == "__main__":
    unittest.main()
