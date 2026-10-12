"""Execute coverage lifecycle hooks with injected bindings and owner changes."""
from copy import deepcopy
import unittest

from tests._generated import _blocks_for_token, generated_fixture
from tests._governor_script_vm import GovernorScriptVM, parse


COUNT = "eu5ab_diag_covered_locations"
INITIALIZED = "eu5ab_template_coverage_initialized"
CONTRIBUTOR = "eu5ab_template_coverage_owner"
ENSURE = "eu5ab_ensure_template_coverage"
REGISTER = "eu5ab_register_location_for_scan"
CLEAR = "eu5ab_clear_location_policy"
TRANSFER = "eu5ab_on_location_changed_owner"


class CoverageVM(GovernorScriptVM):
    def __init__(self, definitions):
        super().__init__({}, {}, {}, {}, (), (), None)
        self.definitions = definitions
        self.human = {self.ROOT: True, "other": True}
        for entity in ("other", "a", "b", "c", "d"):
            self.vars[entity], self.lists[entity] = {}, {}
        self.owners = dict.fromkeys(("a", "b", "c", "d"), self.ROOT)
        self.vars["a"]["eu5ab_policy_id"] = 1
        self.vars["b"].update(eu5ab_policy_id=100, eu5ab_template_slot=1,
                              eu5ab_build_cooldown=2)
        self.vars[self.ROOT]["eu5ab_template_slot_1_paused"] = 1
        self.owned_passes = 0

    def run(self, name, root="country", **scopes):
        previous = self.ROOT
        self.ROOT = root
        self.local, self.scopes = {}, scopes
        self.operations = 0
        try:
            self.execute(self.definitions[name], [root])
        finally:
            self.ROOT = previous

    def test(self, key, op, value, stack):
        if key == "is_human":
            return self.human.get(stack[-1], False) == (value == "yes")
        return super().test(key, op, value, stack)

    def execute(self, entries, stack):
        index = 0
        while index < len(entries):
            key, op, body = entries[index]
            end = index + 1
            if key == "if":
                while end < len(entries) and entries[end][0] in ("else_if", "else"):
                    end += 1
            if key == "every_owned_location":
                self.owned_passes += 1
                for location, owner in tuple(self.owners.items()):
                    if owner == stack[-1]:
                        self.execute(body, stack + [location])
            elif key == "owner" or key.startswith(("scope:", "var:")):
                target = self.target(key, stack)
                if target is not None:
                    self.execute(body, stack + [target])
                elif op != "?=":
                    raise AssertionError(f"Missing required scope {key}")
            else:
                super().execute(entries[index:end], stack)
            index = end


class TemplateCoverageRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = generated_fixture()
        names = (ENSURE, REGISTER, CLEAR, "eu5ab_unregister_location_from_scan",
                 "eu5ab_sync_location_template_coverage",
                 "eu5ab_remove_location_template_coverage")
        cls.definitions = {
            name: parse(_blocks_for_token(fixture.effects, "\n" + name + " = ")[0])[0][2]
            for name in names
        }
        callback = parse(_blocks_for_token(fixture.on_actions, "\n" + TRANSFER + " = ")[0])[0][2]
        cls.definitions[TRANSFER] = next(body for key, _, body in callback if key == "effect")

    def test_binding_replacement_and_removal_count_each_location_once(self):
        vm = CoverageVM(self.definitions)
        vm.run(REGISTER, "a")
        vm.run(REGISTER, "b")
        self.assertEqual(vm.vars[vm.ROOT][COUNT], 2)  # Includes paused, cooling b.
        vm.vars["a"].update(eu5ab_policy_id=100, eu5ab_template_slot=2)
        for _ in range(2):
            vm.run(REGISTER, "a")
        self.assertEqual(vm.vars[vm.ROOT][COUNT], 2)
        self.assertEqual(sum(len(values) for key, values in vm.lists[vm.ROOT].items()
                             if key.startswith("eu5ab_scan_bucket_")), 2)
        vm.vars["c"]["eu5ab_policy_id"] = 3
        vm.run(REGISTER, "c")
        self.assertEqual(vm.vars[vm.ROOT][COUNT], 3)
        for location, expected in (("a", 2), ("a", 2), ("b", 1), ("c", 0)):
            vm.run(CLEAR, location)
            self.assertEqual(vm.vars[vm.ROOT][COUNT], expected)
            self.assertNotIn(CONTRIBUTOR, vm.vars[location])
            self.assertNotIn("eu5ab_policy_id", vm.vars[location])
        self.assertEqual(vm.owned_passes, 1)

    def test_legacy_counter_is_recounted_once_without_touching_saved_work(self):
        vm = CoverageVM(self.definitions)
        vm.vars[vm.ROOT].update({COUNT: 1, "eu5ab_scan_bucket_day": 7,
                                "eu5ab_scan_start_bucket": 17,
                                "eu5ab_global_budget_remaining": 500,
                                "eu5ab_deep_score_attempts": 240})
        vm.vars["a"]["eu5ab_scan_bucket"] = 9
        vm.vars["c"]["eu5ab_policy_id"] = 2
        vm.owners["c"] = "other"
        vm.lists[vm.ROOT].update(eu5ab_scan_bucket_9_locations=["a"],
                                eu5ab_worker_pending_locations=["b"])
        before = deepcopy((vm.vars, vm.lists))
        vm.run(ENSURE)
        self.assertEqual(vm.vars[vm.ROOT][COUNT], 2)
        for entity in vm.vars:
            ignored = {COUNT, INITIALIZED} if entity == vm.ROOT else {CONTRIBUTOR}
            self.assertEqual({k: v for k, v in vm.vars[entity].items() if k not in ignored},
                             {k: v for k, v in before[0][entity].items() if k not in ignored})
        self.assertEqual(vm.lists, before[1])
        after = deepcopy((vm.vars, vm.lists))
        vm.run(ENSURE)
        self.assertEqual((vm.vars, vm.lists), after)
        self.assertEqual(vm.owned_passes, 1)

    def test_removal_before_legacy_load_initialization_uses_full_coverage(self):
        vm = CoverageVM(self.definitions)
        vm.vars[vm.ROOT][COUNT] = 268
        vm.run(CLEAR, "a")
        self.assertEqual(vm.vars[vm.ROOT][COUNT], 1)
        self.assertEqual(vm.vars["b"][CONTRIBUTOR], vm.ROOT)

    def test_batched_owner_changes_update_both_countries_including_ai(self):
        for human in (False, True):
            for initialized in (False, True):
                with self.subTest(human=human, initialized=initialized):
                    vm = CoverageVM(self.definitions)
                    vm.run(REGISTER, "a")
                    vm.run(REGISTER, "b")
                    vm.owners["c"] = "other"
                    vm.vars["c"]["eu5ab_policy_id"] = 2
                    vm.human["other"] = human
                    if initialized:
                        vm.run(ENSURE, "other")
                    # Native ownership may change for the whole province first.
                    vm.owners.update(a="other", b="other", d="other")
                    for location in ("a", "b", "d"):
                        vm.run(TRANSFER, location, loser=vm.ROOT, winner="other")
                    self.assertEqual(vm.vars[vm.ROOT][COUNT], 0)
                    self.assertEqual(vm.vars["other"][COUNT], 3)
                    for location in ("a", "b", "c"):
                        self.assertEqual(vm.vars[location][CONTRIBUTOR], "other")
                    self.assertNotIn(CONTRIBUTOR, vm.vars["d"])
                    self.assertFalse(any(vm.lists[vm.ROOT].values()))
                    vm.run(TRANSFER, "a", loser=vm.ROOT, winner="other")
                    self.assertEqual(vm.vars["other"][COUNT], 3)


if __name__ == "__main__":
    unittest.main()
