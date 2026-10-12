"""Execute the emitted capacity, ranking, validation and fire guards.

Native UI readings and building identities are fixtures, not an engine test.
Arithmetic is truncated to EU5's five decimal places after each operation.
"""
from decimal import Decimal, ROUND_DOWN
from itertools import product
from functools import cache
import math
import re
import unittest

from src.eu5autobuild import building_capacity as capacity
from src.eu5autobuild.engine import (
    AutomationContext, BuildingCandidate, LocationState, PauseReason,
    candidate_capacity_factor, first_blocking_reason, score_candidate_components,
)
from src.eu5autobuild.rules import AutomationRules
from tests import _generated
from tests._governor_script_vm import parse
from tests.test_engine import RULES, policy
from tests.test_queue_recovery_runtime import QueueVM
from tests._game_data_fixtures import cached_game_data


@cache
def generated_capacity():
    fixture = _generated.generated_fixture()
    names = re.findall(r'^(eu5ab_\w+) = \{', capacity.render_effects() + capacity.render_guis(), re.M)
    names.append('eu5ab_finish_native_recipe_capture')
    names.append('eu5ab_prepare_active_recipe_catalog_view')
    names.extend(('eu5ab_request_upgrade_snapshot', 'eu5ab_prepare_rgo_pending_start'))
    selected = '\n'.join(_generated._blocks_for_token(
        fixture.effects + '\n' + fixture.scripted_guis, '\n' + name + ' = ')[0] for name in names)
    selected = re.sub(r'saved_scopes = \{[^}]*\}', '', selected)
    trigger_names = re.findall(r'^(eu5ab_\w+) = \{', capacity.render_triggers(), re.M)
    trigger_names.append('eu5ab_candidate_replaces_capacity_building')
    trigger_names.append('eu5ab_candidate_replaces_capacity_building_worker_live')
    predecessor = '\n'.join(_generated._blocks_for_token(
        fixture.triggers, '\n' + name + ' = ')[0] for name in trigger_names)
    return ({k: v for k, _, v in parse(selected)},
            {k: v for k, _, v in parse(predecessor)})


class CapacityVM(QueueVM):
    def __init__(self, fixture, *, drop_zero=False):
        self.drop_zero = drop_zero
        self.employment = {'building': 100, 'old_type': 50}
        self.buildings = {'old': ('old_type', 1, True)}
        self.local_buildings = []
        super().__init__(fixture.effects, fixture.scripted_guis)
        effects, triggers = generated_capacity()
        self.definitions.update(effects)
        from src.eu5autobuild import rgo_queue
        self.definitions.update({k: v for k, _, v in parse(rgo_queue.render_effects())})
        # Execute the actual generated predecessor switch too.
        self.capacity_triggers.update(triggers)
        from src.eu5autobuild import upgrade_queue
        self.capacity_triggers.update({k: v for k, _, v in parse(upgrade_queue.render(cached_game_data()[2])[1])})
        self.vars.update(building={}, old={}, old_type={})
        self.lists.update(building={}, old={}, old_type={})
        self.scopes.update(eu5ab_engine_capacity_used=Decimal(0),
                           eu5ab_engine_capacity_limit=Decimal(100))
        self.native.update({
            'eu5ab_scan_month_current': True,
            'scope:eu5ab_candidate_building.eu5ab_current_candidate_configured_priority': 0,
            'scope:eu5ab_candidate_building.eu5ab_recipe_expected_output_value': 1,
            'eu5ab_engine_candidate_in_current_priority_phase': True,
            'eu5ab_engine_candidate_passes_selected_metric': True,
            'eu5ab_engine_candidate_has_actual_budget': True,
            'eu5ab_engine_candidate_keeps_actual_cash_reserve': True,
            'eu5ab_engine_construction_materials_available': True,
            'eu5ab_engine_candidate_has_emergency_demand': False,
        })
        self.vars[self.ROOT].update(eu5ab_scan_month=7, eu5ab_scan_year=1436)

    def publish(self, location='location', ticket=None):
        self.scopes['eu5ab_capacity_ticket'] = self.vars[location].get('eu5ab_capacity_request', 0) if ticket is None else ticket
        self.run('eu5ab_gui_capture_building_capacity', location)

    @staticmethod
    def fixed(number):
        return Decimal(str(number)).quantize(capacity.QUANTUM, rounding=ROUND_DOWN)

    def normalize_arithmetic(self, number):
        return self.fixed(number)

    def value(self, x, stack):
        if isinstance(x, str):
            if x == 'employment_size':
                return Decimal(self.employment.get(stack[-1], 100))
            if x == 'building_level':
                return Decimal(self.buildings[stack[-1]][1])
            if x.startswith('building_type:'):
                return x
            try:
                return Decimal(x)
            except Exception:
                pass
        result = super().value(x, stack)
        if isinstance(result, (int, float, Decimal)) and not isinstance(result, bool):
            return self.fixed(result)
        return result

    def target(self, word, stack):
        if word == 'location':
            return 'location'
        if word == 'building_type':
            return self.buildings[stack[-1]][0]
        if word.endswith('.owner'):
            return self.owners.get(self.target(word[:-6], stack))
        return super().target(word, stack)

    def test(self, k, op, v, stack):
        if k == 'location' and isinstance(v, list):
            return self.condition(v, stack + [self.target(k, stack)])
        if k == 'any_in_list':
            fields = {a: c for a, _, c in v}
            condition = [entry for entry in v if entry[0] != 'variable']
            return any(self.condition(condition, stack + [location])
                       for location in self.lists[stack[-1]].get(fields['variable'], []))
        if k == 'building_can_be_upgraded_by':
            return self.buildings[stack[-1]][2] and self.value(v, stack) == self.ROOT
        if k == 'any_buildings_in_location':
            return any(self.condition(v, stack + [b]) for b in self.local_buildings)
        if k == 'building_type' and isinstance(v, str):
            return self.buildings[stack[-1]][0] == v
        if k == 'switch':
            cases = {a: c for a, _, c in v}
            key = self.value(cases['trigger'], stack)
            return self.condition(cases[key], stack) if key in cases else False
        return super().test(k, op, v, stack)

    def execute(self, entries, stack):
        index = 0
        while index < len(entries):
            end = index + 1
            if entries[index][0] == 'if':
                while end < len(entries) and entries[end][0] in ('else_if', 'else'):
                    end += 1
            if entries[index][0] == 'every_buildings_in_location':
                body = entries[index][2]
                gate = next(v for k, _, v in body if k == 'limit')
                for building in self.local_buildings:
                    if self.condition(gate, stack + [building]):
                        self.execute([e for e in body if e[0] != 'limit'], stack + [building])
            else:
                super().execute(entries[index:end], stack)
            if self.drop_zero:
                for variables in self.vars.values():
                    for key, value in list(variables.items()):
                        if not isinstance(value, bool) and value == 0:
                            del variables[key]
            index = end

    def capture(self, used=0, limit=100):
        # Native modifier reads return a value; zero/missing capacity fails
        # closed without relying on a GUI scope to represent its existence.
        self.native['modifier:free_building_levels'] = self.fixed(limit or 0)
        for key, value in (('used', used),):
            name = 'eu5ab_engine_capacity_' + key
            if value is None:
                self.scopes.pop(name, None)
            else:
                self.scopes[name] = self.fixed(value)
        self.run('eu5ab_capture_building_capacity')

    def finish_worker_recipe(self):
        # Native phase activation is injected. The finish effect and publication
        # guard execute generated code, with an empty-building fixture here.
        self.vars['location']['eu5ab_native_recipe_capturing'] = 1
        self.run('eu5ab_finish_native_recipe_capture')

    def eligible(self):
        return self.test('eu5ab_engine_candidate_has_capacity', '=', 'yes', ['location'])

    def factor(self):
        return self.value('eu5ab_engine_capacity_factor', ['location'])

    def validate(self, *, profit=False, emergency=False):
        self.vars[self.ROOT].update(eu5ab_q_active=1, eu5ab_q_phase=5,
                                   eu5ab_monthly_build_quota=3, eu5ab_q_approved=0,
                                   eu5ab_constructions_started_this_tick=0,
                                   eu5ab_global_candidate_ranking_mode=2 if profit else 1)
        self.lists['location']['eu5ab_q_phase_5_types'] = ['building']
        self.scopes.update(eu5ab_engine_can_build=True, eu5ab_engine_cost=100,
                           eu5ab_engine_profit=10, eu5ab_engine_income=10,
                           eu5ab_engine_queue_check_stage=5)
        self.native['eu5ab_engine_candidate_passes_selected_metric'] = not emergency
        self.native['eu5ab_engine_candidate_has_emergency_demand'] = emergency
        self.calls.clear()
        self.stubs['eu5ab_approve_engine_candidate'] = lambda: self.calls.append('approved')
        self.stubs['eu5ab_record_actual_profit_candidate'] = lambda: self.calls.append('ranked')
        self.run('eu5ab_gui_queue_try_candidate')
        return self.calls


class BuildingCapacityRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = _generated.generated_fixture()

    def vm(self, **kwargs):
        return CapacityVM(self.fixture, **kwargs)

    def test_late_receipt_finishes_whole_batch_without_next_day_and_old_ticket_is_inert(self):
        vm = self.vm()
        vm.vars[vm.ROOT].update(eu5ab_scan_active=1, eu5ab_scan_parallel=0, eu5ab_scan_finalizing=1)
        vm.vars['second'] = {}
        vm.lists['second'] = {}
        vm.owners['second'] = vm.ROOT
        vm.lists[vm.ROOT]['eu5ab_worker_pending_locations'] = ['location', 'second']
        workers = []
        def complete():
            location = vm.scopes['eu5ab_candidate_location']
            vm.vars[location]['eu5ab_worker_complete'] = 1
            workers.append(location)
        vm.stubs['eu5ab_run_location_worker'] = complete
        vm.stubs['eu5ab_merge_location_worker_results'] = lambda: vm.lists[vm.ROOT]['eu5ab_worker_pending_locations'].clear()
        vm.stubs['eu5ab_finish_regional_development_scan'] = lambda: vm.calls.append('finalize')
        vm.run('eu5ab_request_building_capacity')
        vm.run('eu5ab_request_building_capacity', 'second')
        old = vm.vars['location']['eu5ab_capacity_request']
        vm.run('eu5ab_finish_pending_capacity_workers', vm.ROOT)
        self.assertEqual(workers, [])
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_diag_capacity_waiting'], 2)
        vm.publish('second')
        self.assertEqual(workers, ['second'])
        self.assertEqual(vm.calls, [])
        vm.run('eu5ab_request_building_capacity')  # Load/reissued request gets a fresh ID.
        vm.publish(ticket=old)
        self.assertEqual(workers, ['second'])
        vm.publish()
        self.assertEqual(workers, ['second', 'location'])
        self.assertEqual(vm.calls, ['finalize'])
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_diag_capacity_waiting'], 0)
        vm.publish()
        self.assertEqual(vm.calls, ['finalize'])

    def test_invalid_receipt_and_wrong_month_are_distinct_from_waiting(self):
        vm = self.vm(drop_zero=True)
        vm.vars[vm.ROOT].update(eu5ab_scan_active=1, eu5ab_scan_parallel=0)
        vm.lists[vm.ROOT]['eu5ab_worker_pending_locations'] = ['location']
        vm.stubs['eu5ab_run_location_worker'] = lambda: vm.calls.append('worker')
        vm.run('eu5ab_request_building_capacity')
        vm.vars[vm.ROOT]['eu5ab_scan_month'] = 8
        vm.publish()
        self.assertEqual(vm.calls, [])
        self.assertNotIn('eu5ab_capacity_received', vm.vars['location'])
        vm.run('eu5ab_request_building_capacity')
        vm.native['modifier:free_building_levels'] = 0
        vm.publish()
        self.assertEqual(vm.calls, ['worker'])
        self.assertIn('eu5ab_capacity_received', vm.vars['location'])
        self.assertEqual(vm.vars['location']['eu5ab_capacity_reason'], 2)
        self.assertNotIn('eu5ab_capacity_requested', vm.vars['location'])

    def test_parallel_reader_rejects_stale_capacity_ticket_even_with_legacy_queue(self):
        vm = self.vm()
        name = 'eu5ab_gui_capture_parallel_queue'
        source = _generated._blocks_for_token(self.fixture.scripted_guis, '\n' + name + ' = ')[0]
        vm.definitions[name] = parse(re.sub(r'saved_scopes = \{[^}]*\}', '', source))[0][2]
        vm.vars[vm.ROOT].update(eu5ab_scan_active=1, eu5ab_q_active=1)
        vm.lists[vm.ROOT]['eu5ab_worker_pending_locations'] = ['location']
        vm.native.update(num_civil_constructions=1)
        vm.native['modifier:max_constructions_at_same_time'] = 2
        vm.scopes.update(eu5ab_engine_queue_count=1, eu5ab_engine_queue_has_room=True,
                         eu5ab_engine_parallel_modifier=2)
        vm.run('eu5ab_request_building_capacity')
        old = vm.vars['location']['eu5ab_capacity_request']
        vm.run('eu5ab_request_building_capacity')
        vm.scopes['eu5ab_capacity_ticket'] = old
        vm.run(name)
        self.assertNotIn('eu5ab_parallel_owner', vm.vars['location'])
        vm.scopes['eu5ab_capacity_ticket'] = vm.vars['location']['eu5ab_capacity_request']
        vm.run(name)
        self.assertEqual(vm.vars['location']['eu5ab_parallel_owner'], vm.ROOT)

    def test_finalize_waits_for_sampling_and_month_expiry_reports_unfinished(self):
        vm = self.vm()
        names = ('eu5ab_finish_regional_development_scan', 'eu5ab_expire_old_scan_month')
        for name in names:
            vm.definitions[name] = parse(_generated._blocks_for_token(self.fixture.effects, '\n' + name + ' = ')[0])[0][2]
        vm.vars[vm.ROOT].update(eu5ab_scan_active=1, eu5ab_scan_round_active=1)
        vm.lists[vm.ROOT]['eu5ab_worker_pending_locations'] = ['location']
        vm.run('eu5ab_request_building_capacity')
        vm.stubs['trigger_event_silently'] = lambda: vm.calls.append('retry')
        vm.run('eu5ab_finish_regional_development_scan', vm.ROOT)
        self.assertEqual(vm.calls, ['retry'])
        self.assertIn('eu5ab_scan_active', vm.vars[vm.ROOT])
        self.assertIn('eu5ab_scan_finalizing', vm.vars[vm.ROOT])
        for name in ('eu5ab_settle_saved_approvals', 'eu5ab_clear_location_worker_state',
                     'eu5ab_clear_location_candidate_state', 'eu5ab_clear_engine_candidate_queue',
                     'eu5ab_reset_committed_construction_demand', 'eu5ab_clear_scan_continuation'):
            vm.stubs[name] = lambda: None
        vm.native['eu5ab_scan_month_current'] = False
        vm.run('eu5ab_expire_old_scan_month', vm.ROOT)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_diag_capacity_expired'], 1)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_diag_scan_stalled'], 1)
        self.assertNotIn('eu5ab_scan_active', vm.vars[vm.ROOT])
        self.assertFalse(vm.lists[vm.ROOT]['eu5ab_worker_pending_locations'])

    def test_native_precision_boundaries_match_model(self):
        for maximum in (Decimal('0.00001'), Decimal('0.12347'), Decimal(42),
                        Decimal('42.31417'), Decimal(100), Decimal('80000000000000')):
            readings = {Decimal(0)}
            for boundary in (maximum * Decimal('.95'), maximum * Decimal('1.10')):
                base = CapacityVM.fixed(boundary)
                readings.update((max(Decimal(0), base-capacity.QUANTUM), base, base+capacity.QUANTUM))
            for ratio in ('.96', '1', '1.025', '1.05', '1.099'):
                readings.add(CapacityVM.fixed(maximum * Decimal(ratio)))
            for used in sorted(readings):
                with self.subTest(used=used, limit=maximum):
                    vm = self.vm(drop_zero=True)
                    vm.capture(used, maximum)
                    self.assertEqual(vm.eligible(), used < maximum * Decimal('1.10'))
                    self.assertEqual(float(vm.factor()), capacity.coefficient(used, maximum))
        for used, expected in ((95, 1), (100, .66666), (105, .33333), (110, 0)):
            vm = self.vm()
            vm.capture(used)
            self.assertEqual(float(vm.factor()), expected)

    def test_missing_bad_and_zero_readings_do_not_share_old_snapshot(self):
        for used, limit in ((None, 100), (1, None), (0, 0), (0, -1), (-1, 100)):
            vm = self.vm(drop_zero=True)
            vm.capture(20, 100)
            vm.capture(used, limit)
            self.assertFalse(vm.eligible())
            self.assertNotIn('eu5ab_capacity_ready', vm.vars['location'])
        vm.capture(0, 100)
        self.assertTrue(vm.eligible())
        self.assertEqual(vm.factor(), 1)
        self.assertNotIn('eu5ab_capacity_used', vm.vars['location'])
        for bad in (None, math.nan, math.inf, -math.inf, True):
            self.assertEqual(capacity.coefficient(bad, 100), 0)
            self.assertEqual(capacity.coefficient(0, bad), 0)

    def test_roomy_snapshot_does_not_query_replacement_for_capacity(self):
        class RoomyVM(CapacityVM):
            def test(self, key, op, value, stack):
                if key in ('eu5ab_candidate_capacity_exempt', 'eu5ab_engine_candidate_capacity_exempt'):
                    raise AssertionError('A full factor does not require a predecessor query')
                return super().test(key, op, value, stack)
        vm = RoomyVM(self.fixture)
        vm.capture(95)
        self.assertTrue(vm.eligible())
        self.assertEqual(vm.factor(), 1)
        self.assertEqual(vm.value('eu5ab_candidate_capacity_factor', ['building']), 1)

    def test_signed_ranking_is_monotone_and_cannot_overflow(self):
        for score in (-91_000_000_000_000, -10**9, -20, 0, 20, 10**9):
            previous = Decimal(str(score))
            for used in (90, 95, 100, 105, 109, Decimal('109.99999')):
                vm = self.vm()
                vm.capture(used)
                vm.vars['location']['eu5ab_q_profit_candidate_rank'] = Decimal(score)
                rank = vm.value('eu5ab_capacity_profit_rank', ['location'])
                self.assertLessEqual(rank, previous)
                self.assertGreaterEqual(rank, min(Decimal(score), Decimal(capacity.RANK_FLOOR)))
                expected = capacity.discount(score, float(vm.factor()))
                self.assertAlmostEqual(float(rank), expected, delta=max(.00002, abs(expected)*1e-14))
                previous = rank
        self.assertIsNone(capacity.discount(-10, 0))
        self.assertIsNone(capacity.discount(math.inf, .5))

    def test_hard_gate_covers_both_modes_and_emergency_exceptions(self):
        for profit, emergency, used in product(
            (False, True), (False, True), (109, 110),
        ):
            vm = self.vm()
            vm.capture(used)
            actions = vm.validate(profit=profit, emergency=emergency)
            self.assertEqual(actions, [('ranked' if profit else 'approved')] if used < 110 else [])
            if used == 110:
                self.assertEqual(vm.vars[vm.ROOT]['eu5ab_diag_fail_building_capacity'], 1)

    def test_actual_replacement_survives_employment_change_but_not_lost_predecessor(self):
        vm = self.vm()
        vm.capture(200)
        self.assertFalse(vm.eligible())
        vm.scopes['eu5ab_engine_replaced_building'] = 'old'
        self.assertTrue(vm.eligible())
        self.assertEqual(vm.factor(), 1)
        vm.buildings['old'] = ('old_type', 0, True)
        self.assertFalse(vm.eligible())
        vm.buildings['old'] = ('old_type', 1, False)
        self.assertFalse(vm.eligible())
        vm.buildings['old'] = ('old_type', 1, True)
        vm.employment['old_type'] = 0
        self.assertFalse(vm.eligible())
        vm.employment['building'] = 0
        self.assertTrue(vm.eligible())
        vm.capture(None, None)
        self.assertTrue(vm.eligible())

    def test_generated_predecessor_switch_checks_real_source_and_owner(self):
        destination, predecessors = next((key, values) for key, values in
                                         cached_game_data()[2].predecessors.items() if values)
        vm = self.vm()
        destination = 'building_type:' + destination
        source = 'building_type:' + predecessors[0]
        vm.vars[destination], vm.vars[source] = {}, {}
        vm.buildings['old'] = (source, 1, True)
        vm.local_buildings = ['old']
        vm.capture(200)
        self.assertTrue(vm.test('eu5ab_candidate_has_capacity', '=', 'yes', [destination]))
        for levels, allowed, employment in ((0, True, 100), (1, False, 100), (1, True, 0)):
            vm.buildings['old'] = (source, levels, allowed)
            vm.employment[source] = employment
            self.assertFalse(vm.test('eu5ab_candidate_has_capacity', '=', 'yes', [destination]))

    def prepare_fire(self, vm):
        vm.vars[vm.ROOT].update(eu5ab_q_active=1, eu5ab_q_fire=1,
                               eu5ab_q_planned_spend=100, eu5ab_q_planned_budget=100)
        vm.vars['location'].update(eu5ab_q_location_approved=1, eu5ab_q_approved_cost=100)
        vm.lists['location']['eu5ab_q_approved_types'] = ['building']
        vm.scopes['eu5ab_engine_cost'] = 100
        vm.native.update(gold=1000, eu5ab_current_min_cash_reserve=50)
        vm.native['scope:eu5ab_candidate_location.eu5ab_current_min_cash_reserve'] = 50

    def test_fire_ignores_capacity_and_slot_changes_but_cannot_issue_twice(self):
        vm = self.vm()
        vm.capture(50)
        self.prepare_fire(vm)
        vm.scopes['eu5ab_engine_can_build'] = True
        vm.run('eu5ab_gui_queue_request_fire')
        guard = dict((k, v) for k, _, v in vm.definitions['eu5ab_gui_queue_fire_permitted'])['is_shown']
        self.assertTrue(vm.condition(guard, ['location']))
        vm.scopes['eu5ab_engine_capacity_used'] = Decimal(110)
        self.assertTrue(vm.condition(guard, ['location']))
        vm.scopes['eu5ab_engine_replaced_building'] = 'old'
        self.assertTrue(vm.condition(guard, ['location']))
        vm.buildings['old'] = ('old_type', 0, True)
        self.assertTrue(vm.condition(guard, ['location']))
        vm.scopes['eu5ab_engine_capacity_used'] = Decimal(100)
        self.assertTrue(vm.condition(guard, ['location']))
        vm.native['num_civil_constructions'] = 1
        self.assertTrue(vm.condition(guard, ['location']), 'Slot changes are no longer guarded at fire')
        vm.vars['location']['eu5ab_q_fire_issued'] = 1
        self.assertFalse(vm.condition(guard, ['location']), 'Never fire twice before confirmation')

    def test_zero_queue_baseline_remains_valid_when_numeric_zero_is_absent(self):
        vm = self.vm(drop_zero=True)
        vm.capture(50)
        self.prepare_fire(vm)
        vm.scopes['eu5ab_engine_can_build'] = True
        vm.run('eu5ab_gui_queue_request_fire')
        guard = dict((k, v) for k, _, v in vm.definitions['eu5ab_gui_queue_fire_permitted'])['is_shown']
        self.assertNotIn('eu5ab_q_queue_before', vm.vars['location'])
        self.assertTrue(vm.condition(guard, ['location']))
        vm.native['num_civil_constructions'] = 1
        self.assertTrue(vm.condition(guard, ['location']))
        vm.stubs['eu5ab_commit_engine_candidate_budget'] = lambda: vm.calls.append('commit')
        vm.native['location_building_level(scope:eu5ab_candidate_building)'] = 1
        vm.vars['location']['eu5ab_q_fire_issued'] = 1
        vm.run('eu5ab_confirm_engine_candidate')
        self.assertEqual(vm.calls, ['commit'])
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_constructions_started_this_tick'], 1)

    def test_repeat_fire_callback_cannot_replace_the_precommand_upgrade_baseline(self):
        vm = self.vm()
        self.prepare_fire(vm)
        vm.scopes['eu5ab_engine_replaced_building'] = 'old'
        vm.native['eu5ab_pending_exact_predecessor'] = True
        vm.native['scope:eu5ab_engine_replaced_building.building_level'] = 3
        snapshots = []
        # Confirmation accounting has its own queue tests. This fixture checks
        # that a repeated data sample retains the pre-command upgrade geometry.
        vm.stubs['eu5ab_confirm_engine_candidate'] = lambda: None
        vm.scopes['eu5ab_engine_can_build'] = True
        vm.stubs['eu5ab_pf_capture_start_geometry'] = lambda: snapshots.append('capture')
        vm.run('eu5ab_gui_queue_request_fire')
        self.assertEqual(vm.vars['location']['eu5ab_pending_predecessor_before'], 3)
        vm.vars['location']['eu5ab_q_fire_issued'] = 1
        vm.native['scope:eu5ab_engine_replaced_building.building_level'] = 2
        vm.native['eu5ab_pending_exact_predecessor'] = False
        vm.run('eu5ab_gui_queue_request_fire')
        self.assertEqual(vm.vars['location']['eu5ab_pending_predecessor_before'], 3)
        self.assertEqual(vm.vars['location']['eu5ab_pending_predecessor'], 'old')
        self.assertEqual(snapshots, ['capture'])

    def test_profit_order_discounted_once_true_profit_preserved_and_zero_is_a_rank(self):
        vm = self.vm(drop_zero=True)
        vm.capture('102.5')
        vm.scopes['eu5ab_engine_profit'] = 10
        vm.run('eu5ab_record_actual_profit_candidate')
        self.assertEqual(vm.vars['location']['eu5ab_q_profit_best_rank'], 5)
        self.assertEqual(vm.vars['location']['eu5ab_q_profit_best_actual'], 10)
        vm.lists['location']['eu5ab_q_profit_best_types'] = []
        vm.scopes['eu5ab_engine_profit'] = 0
        vm.run('eu5ab_record_actual_profit_candidate')
        self.assertNotIn('eu5ab_q_profit_best_rank', vm.vars['location'])
        vm.scopes['eu5ab_engine_profit'] = -1
        vm.scopes['eu5ab_candidate_building'] = 'worse'
        vm.run('eu5ab_record_actual_profit_candidate')
        self.assertEqual(vm.lists['location']['eu5ab_q_profit_best_types'], ['building'])

    def test_capacity_waiting_retry_and_delayed_worker_are_one_shot(self):
        for parallel, capture in product((0, 1), (False, True)):
            vm = self.vm()
            vm.vars[vm.ROOT].update(eu5ab_scan_active=1, eu5ab_scan_parallel=parallel)
            vm.lists[vm.ROOT]['eu5ab_worker_pending_locations'] = ['location']
            vm.stubs['eu5ab_run_location_worker'] = lambda: vm.calls.append('worker')
            vm.stubs['trigger_event_silently'] = lambda: vm.calls.append('scheduled')
            vm.run('eu5ab_request_building_capacity')
            if capture:
                vm.finish_worker_recipe()
                vm.publish()
            vm.run('eu5ab_finish_pending_capacity_workers', vm.ROOT)
            vm.run('eu5ab_run_capacity_worker_once')
            self.assertEqual(vm.calls.count('worker'), int(capture))
            self.assertEqual(vm.calls.count('scheduled'), int(bool(parallel and capture)))
            self.assertEqual(vm.eligible(), capture)
            self.assertEqual('eu5ab_capacity_requested' in vm.vars['location'], not capture)
            self.assertEqual('eu5ab_capacity_worker_country' in vm.vars['location'], not capture)

    def capacity_shown(self, vm, gui, root):
        return vm.condition(dict((k, v) for k, _, v in vm.definitions[gui])['is_shown'], [root])

    def test_completed_workers_retained_for_merge_do_not_send_native_gui_commands(self):
        # Native profiler: 30 completed workers sent 30 begin.Execute calls per
        # paused frame. Their merge data must survive without any recipe reader.
        from copy import deepcopy
        from tests._gui_callbacks import GuiBridge, check, expression
        from src.eu5autobuild.script_syntax import parse as gui_parse, render
        vm = self.vm()
        vm.vars[vm.ROOT]['eu5ab_scan_active'] = 1
        locations = ['location'] + [f'completed_{i}' for i in range(29)]
        vm.lists[vm.ROOT]['eu5ab_worker_pending_locations'] = locations[:]
        for location in locations:
            vm.vars[location] = dict(eu5ab_worker_complete=1, eu5ab_capacity_ready=1,
                                     eu5ab_capacity_limit=100, eu5ab_worker_diag_candidates=7)
            vm.owners[location] = vm.ROOT
            vm.lists[location] = {}
        before = deepcopy(vm.vars), deepcopy(vm.lists)
        self.assertFalse(self.capacity_shown(vm, 'eu5ab_gui_capacity_requests_exist', vm.ROOT))
        bridge = GuiBridge(vm)
        bridge.guis.update({k: {a: c for a, _, c in v} for k, _, v in gui_parse(capacity.render_guis())})
        widgets = gui_parse(capacity.render_capture_widget())
        rows = dict((k, v) for k, _, v in widgets[-1][2])['item'][0][2]
        guard = next(v for k, _, v in rows if k == 'widget')
        model = dict((k, v) for k, _, v in guard)['datamodel'].strip('"')
        self.assertEqual(check(expression(model)), '[unregistered]')
        # Preserve the row's Location and Scope; do not evaluate any guarded
        # native recipe/Building expression when the request is already gone.
        row_widget = render([('widget', '=', rows)])
        for location in locations:
            self.assertFalse(self.capacity_shown(vm, 'eu5ab_gui_capacity_request_pending', location))
            self.assertEqual(bridge.callbacks(row_widget, location,
                             animation='eu5ab_worker_parallel_sample'), [])
            vm.publish(location)
        self.assertEqual(bridge.building_reads, [])
        self.assertEqual((vm.vars, vm.lists), before)

    def test_worker_gui_request_gate_tracks_capture_retry_owner_and_load(self):
        vm = self.vm()
        vm.vars[vm.ROOT].update(eu5ab_scan_active=1, eu5ab_scan_parallel=0)
        vm.lists[vm.ROOT]['eu5ab_worker_pending_locations'] = ['location', 'completed']
        vm.vars['completed'] = {'eu5ab_worker_complete': 1, 'eu5ab_capacity_ready': 1}
        vm.lists['completed'] = {}
        vm.owners['completed'] = vm.ROOT
        vm.vars['location']['eu5ab_worker_complete'] = 1
        vm.run('eu5ab_request_building_capacity')
        self.assertTrue(self.capacity_shown(vm, 'eu5ab_gui_capacity_requests_exist', vm.ROOT))
        self.assertTrue(self.capacity_shown(vm, 'eu5ab_gui_capacity_request_pending', 'location'))
        vm.vars[vm.ROOT]['eu5ab_scan_resume_after_load'] = 1
        self.assertFalse(self.capacity_shown(vm, 'eu5ab_gui_capacity_requests_exist', vm.ROOT))
        self.assertFalse(self.capacity_shown(vm, 'eu5ab_gui_capacity_request_pending', 'location'))
        del vm.vars[vm.ROOT]['eu5ab_scan_resume_after_load']
        vm.vars['other_country'] = {'eu5ab_scan_active': 1}
        vm.lists['other_country'] = {'eu5ab_worker_pending_locations': ['location']}
        vm.owners['location'] = 'other_country'
        self.assertFalse(self.capacity_shown(vm, 'eu5ab_gui_capacity_requests_exist', vm.ROOT))
        self.assertFalse(self.capacity_shown(vm, 'eu5ab_gui_capacity_request_pending', 'location'))
        # Even a valid new owner's request must not be read by the old GUI.
        vm.run('eu5ab_request_building_capacity')
        self.assertFalse(self.capacity_shown(vm, 'eu5ab_gui_capacity_requests_exist', vm.ROOT))
        self.assertFalse(self.capacity_shown(vm, 'eu5ab_gui_capacity_request_pending', 'location'))
        vm.owners['location'] = vm.ROOT
        vm.run('eu5ab_request_building_capacity')
        vm.stubs['eu5ab_run_location_worker'] = lambda: vm.calls.append('worker')
        vm.finish_worker_recipe()
        vm.publish()
        self.assertEqual(vm.calls, ['worker'])
        self.assertFalse(self.capacity_shown(vm, 'eu5ab_gui_capacity_request_pending', 'location'))
        self.assertFalse(self.capacity_shown(vm, 'eu5ab_gui_capacity_requests_exist', vm.ROOT))
        vm.publish()
        self.assertEqual(vm.calls, ['worker'])
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_worker_pending_locations'], ['location', 'completed'])
        self.assertEqual(vm.vars['completed'], {'eu5ab_worker_complete': 1, 'eu5ab_capacity_ready': 1})
        vm.run('eu5ab_request_building_capacity')
        self.assertTrue(self.capacity_shown(vm, 'eu5ab_gui_capacity_request_pending', 'location'))
        vm.lists[vm.ROOT]['eu5ab_worker_pending_locations'].clear()
        self.assertFalse(self.capacity_shown(vm, 'eu5ab_gui_capacity_request_pending', 'location'))

    def test_capacity_publication_reads_script_recipe_before_running_worker(self):
        vm = self.vm()
        vm.vars[vm.ROOT].update(eu5ab_scan_active=1, eu5ab_scan_parallel=0)
        vm.lists[vm.ROOT]['eu5ab_worker_pending_locations'] = ['location']
        vm.stubs['eu5ab_run_location_worker'] = lambda: vm.calls.append('worker')
        vm.stubs['eu5ab_refresh_native_recipes'] = lambda: vm.calls.append('recipe')
        vm.run('eu5ab_request_building_capacity')
        vm.publish()
        vm.publish()
        self.assertEqual(vm.calls, ['recipe', 'worker'])
        self.assertFalse(self.capacity_shown(vm, 'eu5ab_gui_capacity_requests_exist', vm.ROOT))
        vm.publish()
        self.assertEqual(vm.calls, ['recipe', 'worker'])

    def test_closed_current_catalog_skips_recipe_capture_unless_candidate_is_exempt(self):
        for jobs, expected in ((100, ['clear']), (0, ['recipe'])):
            with self.subTest(jobs=jobs):
                vm = self.vm()
                vm.vars[vm.ROOT]['eu5ab_scan_active'] = 1
                vm.employment['building'] = jobs

                def prepare():
                    vm.lists['location']['eu5ab_active_recipe_catalog_view'] = ['building']
                    vm.vars['location'].update(
                        eu5ab_active_recipe_catalog_ready=1,
                        eu5ab_active_recipe_catalog_country=vm.ROOT,
                        eu5ab_active_recipe_catalog_month=7,
                        eu5ab_active_recipe_catalog_year=1436,
                    )

                vm.stubs['eu5ab_prepare_active_recipe_catalog_view'] = prepare
                vm.stubs['eu5ab_refresh_native_recipes'] = lambda: vm.calls.append('recipe')
                vm.stubs['eu5ab_clear_native_recipes'] = lambda: vm.calls.append('clear')
                vm.calls.clear()
                vm.capture(200)
                self.assertEqual(vm.calls, expected)

    def test_delayed_parallel_event_waits_for_new_request_to_be_captured(self):
        vm = self.vm()
        event = next(body for name, _, body in parse(self.fixture.events) if name == 'eu5ab_worker.1')
        immediate = next(body for name, _, body in event if name == 'immediate')
        vm.vars[vm.ROOT].update(eu5ab_scan_active=1, eu5ab_scan_parallel=1)
        vm.lists[vm.ROOT]['eu5ab_worker_pending_locations'] = ['location']
        vm.stubs['eu5ab_run_location_worker'] = lambda: vm.calls.append('worker')
        vm.stubs['trigger_event_silently'] = lambda: vm.calls.append('scheduled')
        vm.run('eu5ab_request_building_capacity')
        vm.execute(immediate, ['location'])
        self.assertEqual(vm.calls, [])
        self.assertIn('eu5ab_capacity_worker_country', vm.vars['location'])
        vm.finish_worker_recipe()
        vm.publish()
        vm.execute(immediate, ['location'])
        vm.execute(immediate, ['location'])
        self.assertEqual(vm.calls, ['scheduled', 'worker'])

    def test_offline_model_scale_scope_and_net_occupancy(self):
        context = AutomationContext(location=LocationState(
            fully_staffed_building_levels=50, supported_building_levels=100))
        base = BuildingCandidate('farm', ('wheat',), 10, 1, existing_levels=7)
        self.assertEqual(score_candidate_components(policy(), base, context)['expansion_scale'], 7)
        from dataclasses import replace
        for candidate, bonus in ((base, 7), (replace(base, existing_levels=0), 0),
                                 (replace(base, upgradeable_predecessor_levels=1), 0),
                                 (replace(base, is_rgo=True), 0)):
            parts = score_candidate_components(policy(), candidate, context, RULES)
            self.assertEqual(parts.get('expansion_scale', 0), bonus)
            self.assertNotIn('saturation', parts)
        blocked = replace(context, location=replace(context.location, fully_staffed_building_levels=110))
        self.assertEqual(first_blocking_reason(policy(), base, 100, 2000, context=blocked, rules=RULES),
                         PauseReason.BUILDING_CAPACITY)
        for candidate in (replace(base, is_rgo=True), replace(base, upgradeable_predecessor_levels=1),
                          replace(base, counts_towards_building_capacity=False)):
            self.assertEqual(candidate_capacity_factor(candidate, blocked), 1)
        self.assertEqual(candidate_capacity_factor(base, None), 0)
        self.assertEqual(candidate_capacity_factor(base, replace(context, location=LocationState())), 0)

    def test_legacy_penalties_are_ignored_instead_of_becoming_large_bonuses(self):
        import json
        from src.eu5autobuild.generator import RULES_FILE
        raw = json.loads(RULES_FILE.read_text(encoding='utf-8'))
        raw['schema_version'] = 4
        raw['thresholds'].pop('expansion_bonus_per_level')
        raw['thresholds']['saturation_penalty_per_level'] = 25
        raw['location_scores']['existing_levels_penalty'] = -4
        rules = AutomationRules.from_mapping(raw)
        self.assertEqual(rules.thresholds.expansion_bonus_per_level, 1)
        self.assertFalse(hasattr(rules.thresholds, 'saturation_penalty_per_level'))
        self.assertFalse(hasattr(rules.location_scores, 'existing_levels_penalty'))
