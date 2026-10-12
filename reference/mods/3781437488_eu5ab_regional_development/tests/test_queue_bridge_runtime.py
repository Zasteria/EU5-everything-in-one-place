"""Finite transport and cash-only firing through generated script contracts.

Native widget lifetimes and engine command delivery require in-game validation;
these tests execute synchronous effects with injected native readings.
"""
from copy import deepcopy
from decimal import Decimal
import re
import unittest

from src.eu5autobuild import queue_bridge
from src.eu5autobuild.generator import render_engine_queue_gui
from src.eu5autobuild.script_syntax import parse as syntax_parse
from tests._generated import generated_fixture, _blocks_for_token
from tests._governor_script_vm import parse
from tests.test_queue_recovery_runtime import QueueVM


class BridgeVM(QueueVM):
    def value(self, x, stack):
        if isinstance(x, str):
            try: return Decimal(x)
            except Exception: pass
        return super().value(x, stack)

    def __init__(self):
        fixture = generated_fixture()
        super().__init__(fixture.effects, fixture.scripted_guis)
        names = ('eu5ab_gui_bridge_rgo', 'eu5ab_gui_bridge_confirmation',
                 'eu5ab_gui_queue_request_fire', 'eu5ab_gui_queue_fire_permitted',
                 'eu5ab_gui_capture_parallel_queue', 'eu5ab_gui_clear_parallel_queue',
                 'eu5ab_clear_engine_candidate_queue', 'eu5ab_clear_location_candidate_state',
                 'eu5ab_settle_saved_approvals', 'eu5ab_finish_engine_candidate_queue',
                 'eu5ab_finish_engine_candidate_queue_live', 'eu5ab_clear_worker_screening')
        source = '\n'.join(_blocks_for_token(fixture.effects + '\n' + fixture.scripted_guis,
                          '\n' + name + ' = ')[0] for name in names)
        self.definitions.update({k: v for k, _, v in parse(re.sub(r'saved_scopes = \{[^}]*\}', '', source))})
        self.vars[self.ROOT].update(eu5ab_bridge_schema=1, eu5ab_bridge_rebuild=1,
            eu5ab_q_active=1, eu5ab_q_phase=5, eu5ab_scan_month=7, eu5ab_scan_year=1436,
            eu5ab_q_processed=0, eu5ab_q_expected=0, eu5ab_q_approved=0,
            eu5ab_q_seen=0, eu5ab_q_confirmed=0, eu5ab_monthly_build_quota=10,
            eu5ab_constructions_started_this_tick=0, eu5ab_global_candidate_ranking_mode=0,
            eu5ab_q_planned_spend=0, eu5ab_q_planned_budget=0)
        self.scopes.update(eu5ab_engine_queue_check_stage=5, eu5ab_engine_can_build=False,
                           eu5ab_engine_cost=Decimal('100.12345'))
        self.native.update(eu5ab_pl_today=534430, gold=10000)
        self.native['eu5ab_engine_candidate_in_current_priority_phase'] = True
        self.native['scope:eu5ab_candidate_location.eu5ab_current_min_cash_reserve'] = Decimal('50.00001')
        self.stubs['eu5ab_reset_engine_candidate_watchdog_progress'] = lambda: None
        self.stubs['eu5ab_advance_engine_priority_phase'] = lambda: self.calls.append('advance')
        self.stubs['eu5ab_refresh_planning_queue'] = lambda: self.calls.append('rank')
        self.pool(['location'], [['a', 'b', 'c']])

    def pool(self, locations, types):
        self.lists[self.ROOT]['eu5ab_q_phase_5_locations'] = locations[:]
        for location, buildings in zip(locations, types):
            self.owners[location] = self.ROOT
            self.vars.setdefault(location, {}).update(eu5ab_capacity_ready=1, eu5ab_capacity_open=1,
                                                    eu5ab_capacity_limit=100, eu5ab_capacity_factor=1)
            self.lists.setdefault(location, {})['eu5ab_q_phase_5_types'] = buildings[:]

    def callback(self):
        state = self.vars[self.ROOT]
        self.scopes.update(eu5ab_bridge_ticket=state['eu5ab_bridge_request'],
                           eu5ab_candidate_building=state['eu5ab_bridge_type'])
        self.run('eu5ab_gui_queue_try_candidate', state['eu5ab_bridge_location'])

    def approve_for_fire(self, cost=Decimal('100.12345')):
        self.vars[self.ROOT].update(eu5ab_q_fire=1, eu5ab_q_approved=1, eu5ab_q_seen=1,
                                   eu5ab_q_planned_spend=cost, eu5ab_q_planned_budget=cost)
        self.vars['location'].update(eu5ab_q_location_approved=1, eu5ab_q_approved_cost=cost,
                                     eu5ab_q_material_market='market',
                                     eu5ab_q_approved_profit=Decimal('12.34567'),
                                     eu5ab_q_approved_income=Decimal('14.76543'))
        self.lists['location']['eu5ab_q_approved_types'] = ['a']
        self.lists[self.ROOT]['eu5ab_q_approved_locations'] = ['location']
        self.run('eu5ab_dispatch_queue_bridge', self.ROOT)
        state = self.vars[self.ROOT]
        self.scopes.update(eu5ab_bridge_ticket=state['eu5ab_bridge_request'], eu5ab_candidate_building='a')
        self.stubs['eu5ab_check_engine_confirmation_completion'] = lambda: None


class QueueBridgeRuntimeTests(unittest.TestCase):
    def test_ordered_pool_is_preserved_and_only_unread_head_is_published(self):
        vm = BridgeVM()
        vm.pool(['location', 'second'], [['a', 'b'], ['c']])
        full = deepcopy(vm.lists[vm.ROOT]['eu5ab_q_phase_5_locations']), deepcopy(vm.lists['location']['eu5ab_q_phase_5_types'])
        vm.run('eu5ab_dispatch_queue_bridge', vm.ROOT)
        seen = []
        for _ in range(3):
            state = vm.vars[vm.ROOT]
            seen.append((state['eu5ab_bridge_location'], state['eu5ab_bridge_type'], state['eu5ab_bridge_lane']))
            ticket = state['eu5ab_bridge_request']
            vm.callback()
            after = deepcopy((vm.vars, vm.lists))
            # Duplicate of the preceding request cannot acknowledge the next.
            vm.scopes['eu5ab_bridge_ticket'] = ticket
            vm.run('eu5ab_gui_queue_try_candidate', seen[-1][0])
            self.assertEqual((vm.vars, vm.lists), after)
        self.assertEqual(seen, [('location', 'a', 1), ('location', 'b', 2), ('second', 'c', 1)])
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_processed'], 3)
        self.assertEqual(full, (vm.lists[vm.ROOT]['eu5ab_q_phase_5_locations'], vm.lists['location']['eu5ab_q_phase_5_types']))

    def test_same_phase_retry_load_cancel_and_month_changes_invalidate_tickets(self):
        for change in ('retry', 'load', 'cancel', 'month', 'year', 'owner'):
            with self.subTest(change=change):
                vm = BridgeVM()
                vm.run('eu5ab_dispatch_queue_bridge', vm.ROOT)
                old = vm.vars[vm.ROOT]['eu5ab_bridge_request']
                vm.scopes.update(eu5ab_bridge_ticket=old, eu5ab_candidate_building='a')
                if change == 'retry':
                    vm.run('eu5ab_reset_engine_priority_phase_progress', vm.ROOT)
                    vm.run('eu5ab_dispatch_queue_bridge', vm.ROOT)
                    self.assertGreater(vm.vars[vm.ROOT]['eu5ab_bridge_request'], old)
                elif change == 'load': vm.vars[vm.ROOT]['eu5ab_scan_resume_after_load'] = 1
                elif change == 'cancel': vm.vars[vm.ROOT].pop('eu5ab_q_active')
                elif change in ('month', 'year'): vm.vars[vm.ROOT]['eu5ab_scan_' + change] += 1
                else: vm.owners['location'] = 'foreign'
                before = deepcopy((vm.vars, vm.lists))
                vm.run('eu5ab_gui_queue_try_candidate')
                self.assertEqual((vm.vars, vm.lists), before)

    def test_lost_location_rebuilds_expected_without_mutating_foreign_state(self):
        vm = BridgeVM()
        vm.pool(['location', 'second'], [['a'], ['b']])
        vm.run('eu5ab_dispatch_queue_bridge', vm.ROOT)
        vm.owners['location'] = 'foreign'
        foreign = deepcopy(vm.vars['location'])
        vm.native['eu5ab_pl_today'] += 2
        vm.run('eu5ab_recover_queue_bridge', vm.ROOT)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_bridge_location'], 'second')
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_expected'], 1)
        self.assertEqual(vm.vars['location'], foreign)

    def test_parallel_receipt_is_once_and_does_not_authorize_another_request(self):
        vm = BridgeVM()
        vm.native.update(num_civil_constructions=1)
        vm.scopes.update(eu5ab_engine_queue_count=1, eu5ab_engine_queue_has_room=True)
        vm.run('eu5ab_dispatch_queue_bridge', vm.ROOT)
        state = vm.vars[vm.ROOT]
        old = state['eu5ab_bridge_request']
        vm.scopes.update(eu5ab_bridge_ticket=old, eu5ab_candidate_building='a')
        vm.run('eu5ab_gui_queue_try_candidate')
        self.assertEqual(state['eu5ab_q_processed'], 0)
        # A construction reader has no building-type context or saved scope.
        vm.scopes.pop('eu5ab_candidate_building')
        vm.run('eu5ab_gui_capture_parallel_queue')
        self.assertTrue(state['eu5ab_bridge_parallel_received'])
        vm.callback()
        self.assertNotIn('eu5ab_bridge_parallel_received', state)
        vm.scopes['eu5ab_bridge_ticket'] = old
        before = deepcopy((vm.vars, vm.lists))
        vm.run('eu5ab_gui_capture_parallel_queue')
        self.assertEqual((vm.vars, vm.lists), before)

    def test_fire_refreshes_only_cash_hold_and_preserves_profit_and_other_holds(self):
        vm = BridgeVM()
        vm.approve_for_fire()
        state = vm.vars[vm.ROOT]
        state['eu5ab_q_planned_spend'] += Decimal('60.00001')
        state['eu5ab_q_planned_budget'] += Decimal('60.00001')
        vm.scopes['eu5ab_engine_cost'] = Decimal('101.23456')
        vm.native.update(num_civil_constructions=16, employment_size=100,
                         eu5ab_inputs_available=False, eu5ab_output_not_oversupplied=False,
                         eu5ab_has_local_workforce=False)
        vm.vars['location'].pop('eu5ab_capacity_open', None)
        vm.run('eu5ab_gui_queue_request_fire')
        self.assertEqual(state['eu5ab_q_planned_spend'], Decimal('161.23457'))
        self.assertEqual(vm.vars['location']['eu5ab_q_approved_profit'], Decimal('12.34567'))
        self.assertEqual(vm.vars['location']['eu5ab_q_approved_income'], Decimal('14.76543'))
        gate = dict((k, v) for k, _, v in vm.definitions['eu5ab_gui_queue_fire_permitted'])['is_shown']
        self.assertTrue(vm.condition(gate, ['location']))
        vm.run('eu5ab_record_requested_engine_fire')
        self.assertFalse(vm.condition(gate, ['location']))
        before = deepcopy((vm.vars, vm.lists))
        vm.run('eu5ab_gui_queue_request_fire')
        vm.run('eu5ab_record_requested_engine_fire')
        self.assertEqual((vm.vars, vm.lists), before)

    def test_cash_failure_releases_once_and_never_publishes_confirmation(self):
        vm = BridgeVM()
        vm.approve_for_fire()
        vm.native['gold'] = Decimal('150.12345')  # One fixed unit below quote + reserve.
        vm.run('eu5ab_gui_queue_request_fire')
        self.assertNotIn('eu5ab_q_fire_issued', vm.vars['location'])
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_planned_spend'], 0)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_confirmed'], 1)
        before = deepcopy((vm.vars, vm.lists))
        vm.run('eu5ab_gui_queue_request_fire')
        self.assertEqual((vm.vars, vm.lists), before)

    def test_retired_probe_save_flags_do_not_stop_fourth_dispatch(self):
        vm = BridgeVM()
        vm.pool(['location'], [['a', 'b', 'c', 'd']])
        # Old diagnostic flags can persist in saves, but no longer gate work.
        vm.vars[vm.ROOT].update(eu5ab_probe_bridge_enabled=1,
                               eu5ab_probe_bridge_dispatched=3)
        vm.run('eu5ab_dispatch_queue_bridge', vm.ROOT)
        for _ in range(3): vm.callback()
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_processed'], 3)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_bridge_type'], 'd')
        vm.callback()
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_processed'], 4)

    def test_confirmed_start_charges_fresh_quote_once_after_target_growth(self):
        vm = BridgeVM()
        vm.vars[vm.ROOT].update(eu5ab_global_budget_mode=1, eu5ab_global_fixed_annual_budget=1000,
                               eu5ab_global_budget_limit=1000, eu5ab_global_budget_remaining=1000)
        vm.run('eu5ab_ensure_annual_budget', vm.ROOT)
        vm.approve_for_fire()
        vm.scopes['eu5ab_engine_cost'] = Decimal('101.23456')
        vm.run('eu5ab_gui_queue_request_fire')
        vm.run('eu5ab_record_requested_engine_fire')
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_global_budget_remaining'], 1000)
        vm.native['eu5ab_candidate_queued_levels'] = 1
        vm.run('eu5ab_gui_bridge_confirmation')
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_global_budget_remaining'], Decimal('898.76544'))
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_planned_spend'], 0)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_constructions_started_this_tick'], 1)
        before = deepcopy((vm.vars, vm.lists))
        vm.run('eu5ab_gui_bridge_confirmation')
        self.assertEqual((vm.vars, vm.lists), before)

    def test_finished_approved_location_cannot_block_the_next_location(self):
        vm = BridgeVM()
        vm.approve_for_fire()
        vm.run('eu5ab_clear_queue_bridge', vm.ROOT)
        vm.pool(['location', 'second'], [['a'], ['b']])
        vm.lists['location']['eu5ab_q_confirmed_types'] = ['a']
        vm.lists['second']['eu5ab_q_approved_types'] = ['b']
        vm.vars['second']['eu5ab_q_location_approved'] = 1
        vm.lists[vm.ROOT]['eu5ab_q_approved_locations'] = ['location', 'second']
        vm.run('eu5ab_dispatch_queue_bridge', vm.ROOT)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_bridge_location'], 'second')
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_bridge_type'], 'b')

    def test_cancel_settles_issued_physical_start_before_clearing_approvals(self):
        vm = BridgeVM()
        vm.vars[vm.ROOT].update(eu5ab_global_budget_mode=1, eu5ab_global_fixed_annual_budget=1000,
                               eu5ab_global_budget_limit=1000, eu5ab_global_budget_remaining=1000)
        vm.run('eu5ab_ensure_annual_budget', vm.ROOT)
        vm.approve_for_fire()
        vm.run('eu5ab_gui_queue_request_fire')
        vm.run('eu5ab_record_requested_engine_fire')
        vm.native['eu5ab_candidate_queued_levels'] = 1
        vm.stubs['eu5ab_settle_scan_candidate_batch'] = lambda: None
        vm.stubs['eu5ab_reset_committed_construction_demand'] = lambda: None
        vm.run('eu5ab_finish_engine_candidate_queue', vm.ROOT)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_global_budget_remaining'], Decimal('899.87655'))
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_constructions_started_this_tick'], 1)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_planned_spend'], 0)
        self.assertNotIn('eu5ab_bridge_request', vm.vars[vm.ROOT])
        self.assertNotIn('eu5ab_q_active', vm.vars[vm.ROOT])

    def test_zero_quote_and_absent_zero_hold_still_keep_configured_reserve(self):
        vm = BridgeVM()
        vm.approve_for_fire()
        vm.scopes['eu5ab_engine_cost'] = 0
        vm.native['gold'] = Decimal('50.00001')
        vm.run('eu5ab_gui_queue_request_fire')
        vm.vars['location'].pop('eu5ab_q_approved_cost')
        vm.vars[vm.ROOT].pop('eu5ab_q_planned_spend')
        gate = dict((k, v) for k, _, v in vm.definitions['eu5ab_gui_queue_fire_permitted'])['is_shown']
        self.assertTrue(vm.condition(gate, ['location']))
        vm.native['gold'] = 50
        self.assertFalse(vm.condition(gate, ['location']))

    def test_no_phase_pools_or_candidate_pending_and_no_native_integer_coercion(self):
        gui = render_engine_queue_gui()
        syntax_parse(gui)
        self.assertNotIn("GetList('eu5ab_q_phase_", gui)
        self.assertNotIn('_candidate_pending', gui)
        self.assertNotIn('MakeScopeValue(Construction.CountAllInLocation)', gui)
        # Each fire reader requests a quote, with no late economic/capacity read.
        for lane in (1, 2):
            source = gui[gui.index("GetList('eu5ab_bridge_fire_" + str(lane)):
                         gui.index("GetList('eu5ab_bridge_", gui.index("GetList('eu5ab_bridge_fire_" + str(lane)) + 10)]
            for getter in ('GetNumBuildingLevelsWithEmployment', 'GetMaxParallelInQueue',
                           'GetBuildingTypeProfitInLocation', 'CanBuildOrExpandBuilding'):
                self.assertNotIn(getter, source)


if __name__ == '__main__': unittest.main()
