"""Verify approval/diagnostic precedence and query reuse with live generated effects."""
from collections import Counter
from itertools import product
import unittest

from src.eu5autobuild.food_infrastructure import FOOD_BUILDING_FINAL_GATES
from src.eu5autobuild.queue_validation import PREFIX
from tests import _generated as automation
from tests._governor_script_vm import parse
from tests.test_queue_recovery_runtime import QueueVM


OUTPUT = 'scope:eu5ab_candidate_building.eu5ab_recipe_expected_output_value'
METRIC = 'eu5ab_engine_candidate_passes_selected_metric'
DEMAND = 'eu5ab_engine_candidate_has_emergency_demand'
INPUTS = 'eu5ab_inputs_available'
MATERIALS = 'eu5ab_engine_construction_materials_available'


class ValidationVM(QueueVM):
    def __init__(self, fixture):
        super().__init__(fixture.effects, fixture.scripted_guis)
        self.queries = Counter()
        self.live_triggers = {k: v for k, _, v in parse(fixture.triggers)
                              if k in ('eu5ab_engine_candidate_economically_sound',
                                       'eu5ab_engine_candidate_uses_emergency_override')}
        self.result = None
        self.stubs['eu5ab_approve_engine_candidate'] = lambda: self.approve('approve')
        self.stubs['eu5ab_record_actual_profit_candidate'] = lambda: self.approve('record')

    def approve(self, kind):
        self.result = kind
        if kind == 'approve':
            self.vars['location']['eu5ab_q_location_approved'] = True

    def value(self, x, stack):
        if isinstance(x, str) and x in (OUTPUT, METRIC, DEMAND, INPUTS, MATERIALS):
            self.queries[x] += 1
        return super().value(x, stack)

    def test(self, k, op, v, stack):
        if k in self.live_triggers:
            return self.condition(self.live_triggers[k], stack) == (v == 'yes')
        if k == 'OR':
            return any(self.test(*entry, stack) for entry in v)
        if k in ('AND', 'NOT'):
            result = all(self.test(*entry, stack) for entry in v)
            return not result if k == 'NOT' else result
        return super().test(k, op, v, stack)

    def reset_candidate(self, mode=0):
        self.vars[self.ROOT].update({k: 0 for k in self.vars[self.ROOT]
                                     if k.startswith('eu5ab_diag_')})
        self.vars[self.ROOT].update(eu5ab_q_active=1, eu5ab_q_phase=5, eu5ab_q_approved=0,
                                   eu5ab_monthly_build_quota=3, eu5ab_constructions_started_this_tick=0,
                                   eu5ab_global_candidate_ranking_mode=2 if mode == 1 else 1)
        self.vars[self.ROOT].pop('eu5ab_q_profit_selecting', None)
        self.vars[self.ROOT].pop('eu5ab_q_retry_phase', None)
        if mode == 2:
            self.vars[self.ROOT]['eu5ab_q_profit_selecting'] = 1
        self.vars['location'] = {}
        self.run('eu5ab_capture_building_capacity')
        self.lists['location'] = {'eu5ab_q_phase_5_types': ['building'],
                                  'eu5ab_q_profit_best_types': ['building']}
        self.scopes.update(eu5ab_engine_can_build=True, eu5ab_engine_cost=100,
                           eu5ab_candidate_building='building',
                           eu5ab_engine_queue_check_stage=0 if mode == 2 else 5)
        self.native.update({gate: True for gate, _ in FOOD_BUILDING_FINAL_GATES})
        self.native.update({OUTPUT: 1, METRIC: True, DEMAND: False,
                            INPUTS: True, MATERIALS: True,
                            'eu5ab_engine_candidate_in_current_priority_phase': True,
                            'eu5ab_engine_candidate_has_actual_budget': True,
                            'eu5ab_engine_candidate_keeps_actual_cash_reserve': True})
        self.callback = 'eu5ab_gui_queue_try_profit_candidate' if mode == 2 else 'eu5ab_gui_queue_try_candidate'
        self.result = None
        self.queries.clear()


class QueueValidationRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = automation.generated_fixture()

    def test_economics_matches_live_path_and_never_repeats_output_or_metric(self):
        vm = ValidationVM(self.fixture)
        for mode, cost, output, metric, demand in product(range(3), (-1, 0, 100), (-1, 0, 2), (False, True), (False, True)):
            vm.reset_candidate(mode)
            vm.scopes['eu5ab_engine_cost'] = cost
            vm.native.update({OUTPUT: output, METRIC: metric, DEMAND: demand})
            expected = vm.condition(vm.live_triggers['eu5ab_engine_candidate_economically_sound'], ['location'])
            emergency = vm.condition(vm.live_triggers['eu5ab_engine_candidate_uses_emergency_override'], ['location'])
            vm.queries.clear()
            vm.run(vm.callback)
            with self.subTest(mode=mode, cost=cost, output=output, metric=metric, demand=demand):
                self.assertEqual(vm.result, ('record' if mode == 1 else 'approve') if expected else None)
                self.assertEqual(bool(vm.vars['location'].get('eu5ab_q_approved_emergency_override')), expected and emergency)
                self.assertEqual(vm.queries[OUTPUT], int(cost > 0))
                self.assertEqual(vm.queries[METRIC], int(cost > 0 and output > 0))
                self.assertEqual(vm.queries[DEMAND], int(cost > 0 and output > 0 and not metric))
                self.assertFalse(any(k.startswith(PREFIX) for k in vm.vars['location']))

    def test_all_gate_combinations_preserve_original_failure_precedence(self):
        vm = ValidationVM(self.fixture)
        for mode in (0, 2):
            for cheap, vanilla, food, inputs, economic, materials, budget, cash in product((False, True), repeat=8):
                vm.reset_candidate(mode)
                # A prior success does not block a second free local slot.
                # Only a current outstanding approval blocks another candidate.
                if not cheap:
                    vm.vars['location']['eu5ab_q_location_approved'] = True
                vm.scopes['eu5ab_engine_can_build'] = vanilla
                food_gate, food_counter = FOOD_BUILDING_FINAL_GATES[0]
                vm.native.update({food_gate: food, INPUTS: inputs, METRIC: economic, MATERIALS: materials,
                                  'eu5ab_engine_candidate_has_actual_budget': budget,
                                  'eu5ab_engine_candidate_keeps_actual_cash_reserve': cash})
                allowed = all((cheap, vanilla, food, inputs, economic, materials, budget, cash))
                # This is the pre-change diagnostic precedence, which intentionally
                # differs from the main path (inputs precede economics there).
                reasons = ((vanilla, 'eu5ab_diag_fail_vanilla'), (food, food_counter),
                           (economic, 'eu5ab_diag_fail_engine_economics'),
                           (inputs, 'eu5ab_diag_fail_inputs'),
                           (materials, 'eu5ab_diag_fail_construction_materials'),
                           (budget, 'eu5ab_diag_fail_budget'), (cash, 'eu5ab_diag_fail_cash'))
                expected = next((counter for passed, counter in reasons if not passed), None)
                vm.run(vm.callback)
                self.assertEqual(vm.result == 'approve', allowed)
                failures = {k for k, v in vm.vars[vm.ROOT].items() if k.startswith('eu5ab_diag_fail_') and v}
                self.assertEqual(failures, {expected} if expected else set())
                for query in (OUTPUT, METRIC, DEMAND, INPUTS, MATERIALS):
                    self.assertLessEqual(vm.queries[query], 1, (query, reasons))
                self.assertFalse(any(k.startswith(PREFIX) for k in vm.vars['location']))

    def test_next_invocation_rechecks_changed_facts_and_does_not_leak_between_locations(self):
        vm = ValidationVM(self.fixture)
        vm.reset_candidate()
        vm.native[MATERIALS] = False
        vm.run(vm.callback)
        self.assertIsNone(vm.result)
        vm.native[MATERIALS] = True
        vm.lists['location']['eu5ab_q_done_types'] = []
        vm.run(vm.callback)
        self.assertEqual(vm.result, 'approve')
        self.assertEqual(vm.queries[MATERIALS], 2)
        self.assertEqual(vm.queries[OUTPUT], 2)
        # A different candidate/location has its own validation and diagnostics.
        vm.vars['second'] = {}
        vm.owners['second'] = vm.ROOT
        vm.lists['second'] = {'eu5ab_q_phase_5_types': ['second_building']}
        vm.run('eu5ab_capture_building_capacity', 'second')
        vm.scopes['eu5ab_candidate_building'] = 'second_building'
        vm.native[METRIC] = False
        vm.result = None
        vm.run(vm.callback, 'second')
        self.assertIsNone(vm.result)
        self.assertEqual(vm.queries[OUTPUT], 3)
        self.assertTrue(vm.vars['location']['eu5ab_q_location_approved'])
        self.assertFalse(any(k.startswith(PREFIX) for k in vm.vars['second']))

    def test_guarded_duplicate_callback_does_no_expensive_work(self):
        vm = ValidationVM(self.fixture)
        for mode in (0, 2):
            vm.reset_candidate(mode)
            vm.run(vm.callback)
            before = vm.queries.copy()
            vm.run(vm.callback)
            self.assertEqual(vm.queries, before)
