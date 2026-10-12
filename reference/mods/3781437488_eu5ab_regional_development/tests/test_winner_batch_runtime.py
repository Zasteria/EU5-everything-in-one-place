"""Concurrent receipts, ordered reservations, and early start on real scripts."""
from copy import deepcopy
from decimal import Decimal
import unittest

from src.eu5autobuild import winner_batch
from src.eu5autobuild.generator import render_engine_queue_gui
from src.eu5autobuild.script_syntax import parse
from tests.test_quote_cache_runtime import QuoteVM


class WinnerBatchTests(unittest.TestCase):
    def vm(self, count=18):
        vm = QuoteVM(('a',))
        locations = [f'place_{n}' for n in range(count)]
        vm.pool(locations, [['a']] * count)
        for n, place in enumerate(locations):
            vm.lists[place]['eu5ab_q_profit_best_types'] = ['a']
            vm.vars[place]['eu5ab_q_profit_best_rank'] = count - n
        vm.vars[vm.ROOT]['eu5ab_monthly_build_quota'] = count
        vm.run('eu5ab_prepare_actual_profit_selection', vm.ROOT)
        vm.run('eu5ab_dispatch_queue_bridge', vm.ROOT)
        return vm, locations

    def receipt(self, vm, place, can_build=True):
        vm.scopes.update(eu5ab_winner_ticket=vm.vars[place]['eu5ab_winner_ticket'],
                         eu5ab_candidate_building='a', eu5ab_engine_can_build=can_build)
        vm.scopes.update({'eu5ab_engine_' + f: 0 for f in winner_batch.FIELDS})
        vm.scopes.update(eu5ab_engine_cost=Decimal('100.12345'),
                         eu5ab_engine_income=12, eu5ab_engine_profit=10,
                         eu5ab_engine_parallel_modifier=vm.native['modifier:max_constructions_at_same_time'])
        vm.run('eu5ab_gui_capture_winner', place)

    def test_all_18_requested_together_and_out_of_order_receipts_finish_without_date_tick(self):
        vm, places = self.vm()
        state = vm.vars[vm.ROOT]
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_winner_locations_1'], places)
        self.assertEqual(state['eu5ab_q_expected'], 18)
        # A missing higher-ranked row blocks reservation, not collection.
        for place in reversed(places[1:]):
            self.receipt(vm, place)
        self.assertEqual(state['eu5ab_q_processed'], 0)
        self.assertEqual(state['eu5ab_q_approved'], 0)
        self.receipt(vm, places[0])
        self.assertEqual(state['eu5ab_q_processed'], 18)
        self.assertEqual(state['eu5ab_q_approved'], 18)
        self.assertEqual(state['eu5ab_q_seen'], 18)
        self.assertEqual(state['eu5ab_q_planned_spend'], Decimal('100.12345') * 18)
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_q_approved_locations'], places)
        self.assertEqual(state['eu5ab_bridge_kind'], 4)
        self.assertEqual(state['eu5ab_bridge_location'], places[0])
        self.assertNotIn('advance', vm.calls)
        parse(render_engine_queue_gui())
        self.assertNotIn('PdxGuiTriggerAllAnimations', winner_batch.render_widget('GuiScope.SetRoot(Location.MakeScope)'))

    def test_nonempty_queue_waits_for_both_native_receipts_in_either_order(self):
        for first in ('quote', 'parallel'):
            with self.subTest(first=first):
                vm, places = self.vm(2)
                # Reissue the same ranked pool after live occupancy changes.
                vm.native.update(num_civil_constructions=1)
                vm.native['modifier:max_constructions_at_same_time'] = 2
                vm.run('eu5ab_clear_winner_batch', vm.ROOT)
                vm.run('eu5ab_dispatch_queue_bridge', vm.ROOT)
                def parallel():
                    vm.scopes.update(eu5ab_winner_ticket=vm.vars[places[0]]['eu5ab_winner_ticket'],
                        eu5ab_engine_queue_count=1, eu5ab_engine_queue_has_room=True,
                        eu5ab_engine_parallel_modifier=2)
                    vm.run('eu5ab_gui_capture_winner_parallel', places[0])
                steps = [lambda: self.receipt(vm, places[0]), parallel]
                if first == 'parallel': steps.reverse()
                steps[0]()
                self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_processed'], 0)
                steps[1]()
                self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_processed'], 1)
                self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_approved'], 1)
                self.assertEqual(vm.vars[vm.ROOT]['eu5ab_bridge_kind'], 4)

    def test_first_approval_starts_before_all_reads_and_other_reads_continue_during_fire(self):
        vm, places = self.vm(3)
        state = vm.vars[vm.ROOT]
        self.receipt(vm, places[0])
        self.assertEqual((state['eu5ab_q_processed'], state['eu5ab_q_expected']), (1, 3))
        self.assertEqual(state['eu5ab_bridge_kind'], 4)
        # Existing fire is confirmed while the remaining batch is still unread.
        state['eu5ab_q_confirmed'] = 1
        state['eu5ab_constructions_started_this_tick'] = 1
        state['eu5ab_q_planned_spend'] = 0
        state['eu5ab_q_planned_budget'] = 0
        vm.lists[places[0]]['eu5ab_q_confirmed_types'] = ['a']
        vm.run('eu5ab_check_engine_confirmation_completion', vm.ROOT)
        self.assertNotIn('eu5ab_q_fire', state)
        self.assertEqual(state['eu5ab_q_phase'], 5)
        vm.run('eu5ab_clear_queue_bridge', vm.ROOT)
        vm.run('eu5ab_dispatch_queue_bridge', vm.ROOT)
        self.receipt(vm, places[1])
        fire_ticket = state['eu5ab_bridge_request']
        self.receipt(vm, places[2])
        self.assertEqual(state['eu5ab_bridge_request'], fire_ticket)
        self.assertEqual(state['eu5ab_q_processed'], 3)
        self.assertEqual(state['eu5ab_q_approved'], 3)
        self.assertEqual(state['eu5ab_q_seen'], 3)
        self.assertEqual(state['eu5ab_q_planned_spend'], Decimal('100.12345') * 2)
        self.assertNotIn('advance', vm.calls)

    def test_duplicate_and_stale_receipts_cannot_reserve_twice_or_resume_old_batch(self):
        for stale in ('duplicate', 'ticket', 'month', 'owner', 'cancel'):
            with self.subTest(stale=stale):
                vm, places = self.vm(2)
                self.receipt(vm, places[0])
                target = places[0] if stale == 'duplicate' else places[1]
                vm.scopes.update(eu5ab_winner_ticket=vm.vars[vm.ROOT]['eu5ab_winner_ticket'],
                                 eu5ab_candidate_building='a')
                if stale == 'ticket': vm.scopes['eu5ab_winner_ticket'] -= 1
                elif stale == 'month': vm.vars[vm.ROOT]['eu5ab_scan_month'] += 1
                elif stale == 'owner': vm.owners[target] = 'foreign'
                elif stale == 'cancel': vm.run('eu5ab_clear_winner_batch', vm.ROOT)
                before = deepcopy((vm.vars, vm.lists, vm.variable_maps))
                vm.run('eu5ab_gui_capture_winner', target)
                self.assertEqual((vm.vars, vm.lists, vm.variable_maps), before)


if __name__ == '__main__': unittest.main()
