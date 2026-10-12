"""Scan quotations rank a whole phase; only winners enter live validation."""
from copy import deepcopy
from decimal import Decimal
import unittest

from src.eu5autobuild import quote_cache
from src.eu5autobuild.generator import render_engine_queue_gui
from src.eu5autobuild.script_syntax import parse as syntax_parse
from tests._generated import generated_fixture, _blocks_for_token
from tests._governor_script_vm import parse
from tests.test_queue_bridge_runtime import BridgeVM


class QuoteVM(BridgeVM):
    def __init__(self, types=('a', 'b')):
        super().__init__()
        self.pool(['location'], [list(types)])
        self.vars[self.ROOT]['eu5ab_global_candidate_ranking_mode'] = 2
        self.native.update(eu5ab_scan_month_current=True,
            eu5ab_candidate_has_capacity=True,
            eu5ab_engine_candidate_passes_selected_metric=True,
            eu5ab_engine_candidate_has_emergency_demand=False,
            eu5ab_engine_candidate_has_actual_budget=True,
            eu5ab_engine_candidate_keeps_actual_cash_reserve=True,
            eu5ab_engine_construction_materials_available=True)
        self.native.update({
            'scope:eu5ab_candidate_building.eu5ab_current_candidate_configured_priority': 0,
            'scope:eu5ab_candidate_building.eu5ab_candidate_capacity_factor': 1,
            'scope:eu5ab_candidate_building.eu5ab_recipe_expected_output_value': 1})
        self.stubs['eu5ab_ensure_rgo_pending'] = lambda: None
        for name in ('eu5ab_prepare_actual_profit_selection',
                     'eu5ab_restart_engine_priority_phase', 'eu5ab_prepare_engine_priority_phase'):
            source = _blocks_for_token(generated_fixture().effects, '\n' + name + ' = ')[0]
            self.definitions.update({k: v for k, _, v in parse(source)})
        self.run('eu5ab_request_candidate_quotes', 'location')

    def capture(self, building, profit=10, cost=Decimal('100.12345')):
        self.scopes.update(eu5ab_candidate_building=building,
            eu5ab_quote_ticket=self.vars['location']['eu5ab_quote_ticket'])
        for field in quote_cache.FIELDS:
            self.scopes['eu5ab_engine_' + field] = 0
        self.scopes.update(eu5ab_engine_cost=cost, eu5ab_engine_profit=profit,
                           eu5ab_engine_income=Decimal('12.34567'))
        self.run('eu5ab_gui_capture_candidate_quote', 'location')

    def collect(self, profits):
        # Screening occurs before the month-end queue becomes active.
        self.vars[self.ROOT].pop('eu5ab_q_active')
        for building, profit in profits:
            self.capture(building, profit)
        self.vars[self.ROOT]['eu5ab_q_active'] = 1


class QuoteCacheTests(unittest.TestCase):
    def test_legacy_quote_upgrade_uses_fresh_ticket_and_rejects_old_receipt(self):
        vm = QuoteVM()
        vm.vars[vm.ROOT].pop('eu5ab_q_active')
        vm.capture('a', 10)
        old_ticket = vm.vars['location']['eu5ab_quote_ticket']
        vm.vars[vm.ROOT]['eu5ab_batch_schema'] = 1
        name = 'eu5ab_request_candidate_quotes'
        vm.definitions.update({k: v for k, _, v in parse(
            _blocks_for_token(generated_fixture().effects, '\n' + name + ' = ')[0])})
        vm.run('eu5ab_request_candidate_quotes', 'location')
        new_ticket = vm.vars['location']['eu5ab_quote_ticket']
        self.assertGreater(new_ticket, old_ticket)
        self.assertEqual(vm.vars['location']['eu5ab_batch_quote_schema'], 3)
        self.assertEqual(vm.lists['location']['eu5ab_quote_ready_types'], [])
        self.assertEqual(vm.lists['location']['eu5ab_quote_requests'], ['a', 'b'])
        vm.run('eu5ab_request_candidate_quotes', 'location')
        self.assertEqual(vm.vars['location']['eu5ab_quote_ticket'], new_ticket)
        vm.scopes['eu5ab_quote_ticket'] = old_ticket
        before = deepcopy((vm.vars, vm.lists, vm.variable_maps))
        vm.run('eu5ab_gui_capture_candidate_quote')
        self.assertEqual((vm.vars, vm.lists, vm.variable_maps), before)

    def test_old_granary_quote_scores_get_a_new_screening_ticket(self):
        vm = QuoteVM()
        vm.vars[vm.ROOT].pop('eu5ab_q_active')
        vm.capture('a', 10)
        old_ticket = vm.vars['location']['eu5ab_quote_ticket']
        vm.vars[vm.ROOT]['eu5ab_batch_schema'] = 1
        vm.vars['location']['eu5ab_batch_quote_schema'] = 2
        vm.variable_maps['location']['eu5ab_quote_kind'] = {'a': 2}
        vm.variable_maps['location']['eu5ab_quote_adjusted_profit'] = {'a': 999}
        vm.lists['location']['eu5ab_batch_screened_types'] = ['a']
        vm.lists['location']['eu5ab_batch_passed_types'] = ['a']
        names = ('eu5ab_request_candidate_quotes', 'eu5ab_clear_candidate_quotes')
        for name in names:
            vm.definitions.update({k: v for k, _, v in parse(
                _blocks_for_token(generated_fixture().effects, '\n' + name + ' = ')[0])})
        vm.run('eu5ab_request_candidate_quotes', 'location')
        self.assertGreater(vm.vars['location']['eu5ab_quote_ticket'], old_ticket)
        self.assertEqual(vm.vars['location']['eu5ab_batch_quote_schema'], 3)
        self.assertFalse(vm.variable_maps['location'].get('eu5ab_quote_kind'))
        self.assertFalse(vm.variable_maps['location'].get('eu5ab_quote_adjusted_profit'))
        self.assertEqual(vm.lists['location']['eu5ab_batch_passed_types'], [])
        self.assertEqual(vm.lists['location']['eu5ab_quote_requests'], ['a', 'b'])

    def test_zero_negative_and_fixed_precision_quotes_are_read_once_without_holds(self):
        vm = QuoteVM()
        vm.vars[vm.ROOT].pop('eu5ab_q_active')
        vm.capture('a', Decimal('-0.00001'), 0)
        maps = vm.variable_maps['location']
        self.assertEqual(maps['eu5ab_quote_cost']['a'], 0)
        self.assertEqual(maps['eu5ab_quote_profit']['a'], Decimal('-0.00001'))
        self.assertEqual(maps['eu5ab_quote_income']['a'], Decimal('12.34567'))
        self.assertEqual(maps['eu5ab_quote_province_food_balance']['a'], 0)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_planned_spend'], 0)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_approved'], 0)
        before = deepcopy((vm.vars, vm.lists, vm.variable_maps))
        vm.capture('a', 999)
        self.assertEqual((vm.vars, vm.lists, vm.variable_maps), before)
        # Native save serializers may omit zero map entries. The ready marker
        # still identifies a complete successful capture, and zero stays zero.
        maps['eu5ab_quote_cost'].pop('a')
        vm.scopes['eu5ab_candidate_building'] = 'a'
        self.assertEqual(vm.value('eu5ab_cached_quote_cost', ['location']), 0)

    def test_missing_field_and_stale_owner_month_year_ticket_or_calendar_fail_closed(self):
        for change in ('field', 'owner', 'month', 'year', 'ticket', 'calendar', 'cancel'):
            with self.subTest(change=change):
                vm = QuoteVM()
                vm.vars[vm.ROOT].pop('eu5ab_q_active')
                # Prepare a valid callback, then invalidate exactly one part.
                vm.scopes.update(eu5ab_candidate_building='a',
                    eu5ab_quote_ticket=vm.vars['location']['eu5ab_quote_ticket'])
                vm.scopes.update({'eu5ab_engine_' + f: 0 for f in quote_cache.FIELDS})
                if change == 'field': vm.scopes.pop('eu5ab_engine_income')
                elif change == 'owner': vm.owners['location'] = 'foreign'
                elif change in ('month', 'year'): vm.vars[vm.ROOT]['eu5ab_scan_' + change] += 1
                elif change == 'ticket': vm.scopes['eu5ab_quote_ticket'] -= 1
                elif change == 'calendar': vm.native['eu5ab_scan_month_current'] = False
                else: vm.run('eu5ab_clear_candidate_quotes', 'location')
                before = deepcopy((vm.vars, vm.lists, vm.variable_maps))
                vm.run('eu5ab_gui_capture_candidate_quote', 'location')
                self.assertEqual((vm.vars, vm.lists, vm.variable_maps), before)

    def test_128_cached_rows_rank_in_one_dispatch_and_only_winner_is_published(self):
        types = [f'type_{i}' for i in range(128)]
        vm = QuoteVM(types)
        vm.collect(zip(types, map(Decimal, range(128))))
        probes = vm.vars[vm.ROOT]['eu5ab_diag_engine_probes']
        vm.run('eu5ab_dispatch_queue_bridge', vm.ROOT)
        state = vm.vars[vm.ROOT]
        self.assertEqual(len(vm.lists['location']['eu5ab_q_done_types']), 128)
        self.assertEqual(vm.vars['location']['eu5ab_winner_type'], 'type_127')
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_winner_locations_1'], ['location'])
        self.assertEqual(state['eu5ab_q_expected'], 1)
        self.assertEqual(state['eu5ab_q_processed'], 0)  # Fresh winner pass begins.
        self.assertEqual(state['eu5ab_diag_engine_probes'], probes)
        self.assertEqual(state['eu5ab_bridge_sequence'], 1)
        self.assertEqual(state['eu5ab_q_approved'], 0)
        self.assertEqual(state['eu5ab_q_planned_spend'], 0)

    def test_missing_head_waits_without_skipping_or_advancing_and_later_read_resumes(self):
        vm = QuoteVM()
        vm.collect([('b', 20)])
        vm.run('eu5ab_dispatch_queue_bridge', vm.ROOT)
        state = vm.vars[vm.ROOT]
        self.assertTrue(state['eu5ab_quote_waiting'])
        self.assertEqual(state['eu5ab_q_processed'], 0)
        self.assertEqual(state['eu5ab_q_expected'], 2)
        self.assertNotIn('eu5ab_bridge_request', state)
        self.assertNotIn('advance', vm.calls)
        vm.capture('a', 10)
        self.assertEqual(vm.vars['location']['eu5ab_winner_type'], 'b')
        self.assertEqual(vm.lists['location']['eu5ab_q_done_types'], ['a', 'b'])

    def test_live_winner_failure_reselects_runner_up_without_recollecting_quotes(self):
        vm = QuoteVM()
        vm.collect([('a', 20), ('b', 10)])
        vm.run('eu5ab_dispatch_queue_bridge', vm.ROOT)
        state = vm.vars[vm.ROOT]
        vm.scopes.update(eu5ab_candidate_building='a',
            eu5ab_winner_ticket=state['eu5ab_winner_ticket'], eu5ab_engine_can_build=True)
        vm.native['eu5ab_engine_candidate_has_actual_budget'] = False
        vm.run('eu5ab_gui_capture_winner', 'location')
        self.assertEqual(vm.lists['location']['eu5ab_q_failed_types'], ['a'])
        self.assertEqual(state['eu5ab_q_approved'], 0)
        self.assertEqual(state['eu5ab_q_planned_spend'], 0)
        self.assertEqual(vm.vars['location']['eu5ab_winner_type'], 'b')
        self.assertEqual(state['eu5ab_diag_engine_probes'], 3)  # Two scan quotes, one live failure.
        self.assertFalse(vm.lists['location'].get('eu5ab_quote_requests'))

    def test_winner_reads_are_bounded_by_remaining_monthly_quota(self):
        vm = QuoteVM(('a',))
        vm.collect([('a', 10)])
        locations = [f'place_{i}' for i in range(12)]
        vm.pool(locations, [['a']] * len(locations))
        for i, location in enumerate(locations):
            vm.lists[location]['eu5ab_q_profit_best_types'] = ['a']
            vm.vars[location]['eu5ab_q_profit_best_rank'] = i
        vm.vars[vm.ROOT].update(eu5ab_monthly_build_quota=5,
                               eu5ab_constructions_started_this_tick=2)
        vm.run('eu5ab_prepare_actual_profit_selection', vm.ROOT)
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_q_profit_locations'],
                         ['place_11', 'place_10', 'place_9'])
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_expected'], 3)

    def test_cleanup_tracks_quotes_outside_the_final_bounded_pool(self):
        vm = QuoteVM()
        vm.collect([('a', 10), ('b', 20)])
        vm.lists[vm.ROOT]['eu5ab_q_phase_5_locations'] = []
        vm.run('eu5ab_clear_engine_candidate_queue', vm.ROOT)
        self.assertNotIn('eu5ab_quote_ticket', vm.vars['location'])
        self.assertFalse(vm.variable_maps['location'].get('eu5ab_quote_profit'))
        self.assertFalse(vm.lists[vm.ROOT].get('eu5ab_quote_locations'))

    def test_capture_widget_reads_pending_requests_with_an_early_guard(self):
        gui = render_engine_queue_gui()
        syntax_parse(gui)
        callback = next(line for line in gui.splitlines() if 'eu5ab_gui_capture_candidate_quote' in line)
        self.assertIn("GetList('eu5ab_quote_requests')", gui)
        self.assertIn("GetList('eu5ab_quote_pending_locations')", gui)
        self.assertIn("eu5ab_gui_quote_request_pending", gui)
        for getter in ('CanBuildOrExpandBuilding', 'max_constructions_at_same_time'):
            self.assertNotIn(getter, callback)
        for name in quote_cache.FIELDS:
            self.assertIn(".AddScope('eu5ab_engine_" + name + "'", callback)
        self.assertIn("GetList('eu5ab_quote_tickets')", gui)
        self.assertIn("MakeScopeValue(Scope.GetValue)", callback)


if __name__ == '__main__': unittest.main()
