"""Run generated building rejection, policy routing and RGO staging together.

Native candidate pools and non-location RGO gate results are injected. The
location gate, cooldown writes, diagnostic branches and staging are generated
script, not a model of the fix. These tests do not emulate the game engine.
"""

from copy import deepcopy
import unittest

from tests import _generated as automation
from tests import test_candidate_backfill_runtime as backfill_runtime
from tests._governor_script_vm import parse
from tests.test_candidate_backfill_runtime import (
    BackfillVM, ROUTER, MERGE,
)


PENDING = "eu5ab_pending_failure_cooldown"
COOLDOWN = "eu5ab_failure_cooldown"
DIAG = "eu5ab_worker_eu5ab_diag_"


class FailureIsolationVM(BackfillVM):
    def __init__(self, definitions, location_gate, **kwargs):
        super().__init__(definitions, **kwargs)
        self.location_gate = location_gate
        self.vars[self.ROOT]["eu5ab_candidate_priority_rgo"] = 3
        self.civil_constructions = 0
        self.blocked_gate = None
        self.workforce_blocked = False
        self.location_gate_states = []

    def value(self, x, stack):
        if x == "num_civil_constructions":
            return self.civil_constructions
        if isinstance(x, str) and x in (
            "eu5ab_rgo_queue_order_score", "eu5ab_location_need_score",
            "eu5ab_rgo_jobs_per_expansion", "eu5ab_rgo_current_available_workers",
            "eu5ab_rgo_projected_available_workers",
            "eu5ab_rgo_price_factor", "eu5ab_rgo_pending_factor", "eu5ab_rgo_current_labor_factor",
            "eu5ab_rgo_market_pending_quantity", "eu5ab_rgo_pending_limit", "eu5ab_rgo_market_gap",
        ):
            return 1
        return super().value(x, stack)

    def test(self, k, op, v, stack):
        if k == 'eu5ab_location_has_parallel_room':
            return (self.civil_constructions < 1) == (v == 'yes')
        if k == "eu5ab_rgo_location_available":
            self.location_gate_states.append(self.vars[stack[-1]].copy())
            return self.condition(self.location_gate, stack) == (v == "yes")
        if k in (
            "eu5ab_rgo_capacity_available", "eu5ab_rgo_enabled",
            "eu5ab_rgo_finance_available", "eu5ab_rgo_utilization_allowed",
            "eu5ab_rgo_workforce_allowed", "eu5ab_rgo_market_need_present",
            "eu5ab_rgo_score_allowed",
            "eu5ab_rgo_pending_data_available", "eu5ab_rgo_pending_below_limit",
            "eu5ab_rgo_pending_allowed",
        ):
            return (k != self.blocked_gate) == (v == "yes")
        if k == "eu5ab_rgo_food_emergency_enabled":
            return v == "no"
        return super().test(k, op, v, stack)

    def execute(self, entries, stack):
        index = 0
        while index < len(entries):
            k, _, _ = entries[index]
            end = index + 1
            if k == "if":
                while end < len(entries) and entries[end][0] in ("else_if", "else"):
                    end += 1
            super().execute(entries[index:end], stack)
            # Native collection reports a candidate rejected solely by workforce.
            if self.workforce_blocked and k == "eu5ab_collect_current_candidate_pools":
                self.vars[stack[-1]]["eu5ab_had_workforce_blocked_candidate"] = 1
            index = end


class RgoFailureIsolationRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        backfill_runtime.CandidateBackfillRuntimeTests.setUpClass()
        cls.definitions = backfill_runtime.CandidateBackfillRuntimeTests.definitions.copy()
        generated = automation.generated_fixture()
        for name in ("eu5ab_stage_rgo_candidate", "eu5ab_capture_rgo_pending_diagnostics"):
            cls.definitions[name] = parse(automation._blocks_for_token(
                generated.effects, "\n" + name + " = ",
            )[0])[0][2]
        cls.location_gate = parse(automation._blocks_for_token(
            generated.triggers, "\neu5ab_rgo_location_available = ",
        )[0])[0][2]

    def vm(self, failure="inputs", **kwargs):
        vm = FailureIsolationVM(self.definitions, self.location_gate, **kwargs)
        if failure in ("inputs", "oversupply", "success"):
            vm.add_pool("new", 1, inputs=failure != "inputs",
                        output=failure != "oversupply")
        elif failure == "workforce":
            vm.workforce_blocked = True
        else:
            self.assertEqual(failure, "no_legal")
        return vm

    def test_unknown_rgo_enters_its_phase_but_does_not_count_as_usable_reserve(self):
        vm = self.vm('no_legal')
        vm.blocked_gate = 'eu5ab_rgo_pending_data_available'
        vm.run()
        self.assertEqual(vm.vars['location']['eu5ab_worker_phase_7_rgo'], 1)
        self.assertEqual(vm.vars['location'][DIAG + 'rgo_fail_pending_data'], 1)
        self.assertTrue(vm.vars['location']['eu5ab_worker_data_wait'])
        vm.run(MERGE, vm.ROOT)
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_q_phase_7_rgo_unsorted_locations'], ['location'])
        self.assertEqual(vm.vars[vm.ROOT].get('eu5ab_scan_candidate_reserve', 0), 0)

    def assert_rgo_staged(self, vm):
        self.assertEqual(vm.vars["location"].get("eu5ab_worker_phase_7_rgo"), 1)
        self.assertEqual(vm.vars["location"].get(DIAG + "rgo_eligible"), 1)
        self.assertEqual(vm.vars["location"][DIAG + "rgo_fail_location"], 0)

    def test_all_ordinary_failures_allow_rgo_before_cooldown_is_committed(self):
        for mode in (1, 2):
            for enabled in (False, True):
                for policy, slot in ((1, None), (100, 1), (100, 20)):
                    for failure, months in (("inputs", 2), ("oversupply", 3),
                                            ("workforce", 2), ("no_legal", 3)):
                        with self.subTest(mode=mode, backfill=enabled, policy=policy,
                                          slot=slot, failure=failure):
                            vm = self.vm(failure, mode=mode, enabled=enabled)
                            vm.vars["location"]["eu5ab_policy_id"] = policy
                            if slot:
                                vm.vars["location"]["eu5ab_template_slot"] = slot
                            vm.run()
                            self.assert_rgo_staged(vm)
                            self.assertEqual(vm.vars["location"][COOLDOWN], months)
                            self.assertEqual(vm.vars["location"][DIAG + "fail_" + failure], 1)
                            self.assertNotIn(COOLDOWN, vm.location_gate_states[0])
                            self.assertNotIn(PENDING, vm.vars["location"])

    def test_original_eager_write_reproduces_rgo_location_rejection(self):
        vm = self.vm()
        vm.definitions = deepcopy(vm.definitions)

        def restore_eager_writes(entries):
            for k, _, v in entries:
                if k == "set_variable" and isinstance(v, list):
                    v[:] = [(a, op, COOLDOWN if a == "name" and b == PENDING else b)
                            for a, op, b in v]
                if isinstance(v, list):
                    restore_eager_writes(v)

        for entries in vm.definitions.values():
            restore_eager_writes(entries)
        vm.run()
        self.assertEqual(vm.vars["location"].get(DIAG + "rgo_fail_location"), 1)
        self.assertNotIn("eu5ab_worker_phase_7_rgo", vm.vars["location"])

    def test_existing_failure_cooldown_build_cooldown_and_construction_still_block(self):
        for blocker in (COOLDOWN, "eu5ab_build_cooldown", "construction"):
            with self.subTest(blocker=blocker):
                vm = self.vm("success")
                if blocker == "construction":
                    vm.civil_constructions = 1
                else:
                    vm.vars["location"][blocker] = 2
                vm.run()
                self.assertEqual(vm.vars["location"].get(DIAG + "rgo_fail_location"), 1)
                self.assertNotIn("eu5ab_worker_phase_7_rgo", vm.vars["location"])
                if blocker != "construction":
                    self.assertEqual(vm.vars["location"][blocker], 2)

    def test_rgo_own_rejections_still_apply_and_preserve_ordinary_cooldown(self):
        for gate, reason in (("capacity_available", "capacity"), ("enabled", "disabled"),
                             ("finance_available", "finance"), ("utilization_allowed", "utilization"),
                             ("workforce_allowed", "workforce"), ("market_need_present", "market_need")):
            with self.subTest(gate=gate):
                vm = self.vm()
                vm.blocked_gate = "eu5ab_rgo_" + gate
                vm.run()
                self.assertEqual(vm.vars["location"].get(DIAG + "rgo_fail_" + reason), 1)
                self.assertNotIn("eu5ab_worker_phase_7_rgo", vm.vars["location"])
                self.assertEqual(vm.vars["location"][COOLDOWN], 2)
                self.assertNotIn(PENDING, vm.vars["location"])

    def test_success_does_not_inherit_stale_pending_failure(self):
        for effect in ("eu5ab_run_location_worker", ROUTER):
            with self.subTest(effect=effect):
                vm = self.vm("success", enabled=False)
                vm.vars["location"].update({PENDING: 9, "eu5ab_worker_active": 1})
                if effect == ROUTER:
                    # Entering the router directly still requires the real
                    # worker's counter initialization, including explicit zero.
                    for entry in vm.definitions["eu5ab_run_location_worker"]:
                        key, _, value = entry
                        if key == "set_variable" and isinstance(value, list):
                            data = {k: v for k, _, v in value}
                            if data["name"].startswith("eu5ab_worker_"):
                                vm.execute([entry], ["location"])
                vm.run(effect)
                self.assert_rgo_staged(vm)
                self.assertNotIn(COOLDOWN, vm.vars["location"])
                self.assertNotIn(PENDING, vm.vars["location"])
                self.assertEqual(vm.staged(), [(8, "new_1")])

    def test_upstream_failure_and_both_merge_schedules_keep_rgo_candidate(self):
        for parallel in (0, 1):
            with self.subTest(parallel=parallel):
                vm = self.vm()
                # The regular building and its upstream replacement both fail inputs.
                vm.upstream["new"] = ["new_1"]
                vm.vars[vm.ROOT]["eu5ab_scan_parallel"] = parallel
                vm.run()
                self.assertEqual(vm.upstream_calls, 1)
                self.assertEqual(vm.vars["location"][DIAG + "fail_inputs"], 2)
                self.assert_rgo_staged(vm)
                if parallel:
                    vm.local, vm.scopes = {}, {}  # Next-day reducer has fresh scopes.
                vm.run(MERGE, vm.ROOT)
                self.assertEqual(vm.lists[vm.ROOT]["eu5ab_q_phase_7_rgo_unsorted_locations"], ["location"])
                self.assertEqual(vm.vars[vm.ROOT]["eu5ab_q_rgo_staged"], 1)
                self.assertNotIn(PENDING, vm.vars["location"])

    def test_worker_cleanup_discards_pending_cooldown_without_applying_it(self):
        vm = self.vm()
        vm.vars["location"][PENDING] = 3
        vm.run("eu5ab_clear_location_worker_state")
        self.assertNotIn(PENDING, vm.vars["location"])
        self.assertNotIn(COOLDOWN, vm.vars["location"])


if __name__ == "__main__":
    unittest.main()
