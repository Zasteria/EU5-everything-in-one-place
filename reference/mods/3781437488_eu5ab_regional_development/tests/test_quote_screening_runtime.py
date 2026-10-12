"""Screening and callback completion with injected economic/recipe boundaries."""
from collections import Counter
from copy import deepcopy
from decimal import Decimal
import unittest

from src.eu5autobuild.food_infrastructure import FOOD_BUILDING_FINAL_GATES
from tests.test_construction_batch_runtime import BatchVM
from tests.test_engine import RULES
from tests._generated import generated_fixture, _blocks_for_token
from tests._governor_script_vm import parse


class ScreeningVM(BatchVM):
    def __init__(self):
        super().__init__()
        self.work = Counter()
        self.vars[self.ROOT].update(eu5ab_batch_ledger_month=7, eu5ab_batch_ledger_year=1436)
        self.lists[self.ROOT]['eu5ab_batch_markets'] = ['market']
        self.vars['location'].update(eu5ab_batch_failure_month=7, eu5ab_batch_failure_year=1436,
                                    eu5ab_batch_failure_country=self.ROOT)
        self.scopes.update(eu5ab_engine_can_build=True, eu5ab_engine_income=12,
                           eu5ab_engine_profit=10, eu5ab_engine_province_food_balance=0,
                           eu5ab_engine_province_food_natural=0, eu5ab_engine_rgo_revenue=0)
        self.native.update(eu5ab_scan_month_current=True, eu5ab_pending_identity_known=True,
            eu5ab_upgrade_source_available=True,
            eu5ab_food_emergency_enabled=False, eu5ab_engine_candidate_has_emergency_demand=False,
            eu5ab_engine_candidate_passes_selected_metric=True,
            eu5ab_candidate_capacity_factor=1, eu5ab_price_adjusted_candidate_score=20,
            eu5ab_recipe_expected_output_value=1, eu5ab_universal_need_score=30,
            eu5ab_pr_efficiency=1, eu5ab_construction_shortage_factor=1)
        for name in ('eu5ab_prepare_recipe_score_snapshot', 'eu5ab_prepare_candidate_score_snapshot',
                     'eu5ab_prepare_candidate_market_prices',
                     'eu5ab_prepare_recipe_screen_snapshot', 'eu5ab_prepare_candidate_filter_prices',
                     'eu5ab_prepare_quote_production_snapshot', 'eu5ab_batch_snapshot_quote_quantities',
                     'eu5ab_prepare_quote_production_output_quantities', 'eu5ab_prepare_quote_production_input_quantities',
                     'eu5ab_prepare_quote_economy_snapshot',
                     'eu5ab_batch_compute_profit_base', 'eu5ab_prepare_production_reference'):
            self.stubs[name] = lambda: None
        for good in RULES.construction_goods:
            self.native['eu5ab_construction_demand_' + good] = 1

    def target(self, word, stack):
        if word == 'building_type':
            return 'building_type:predecessor'
        return super().target(word, stack)

    def value(self, word, stack):
        if word == 'building_can_be_upgraded_by':
            return self.ROOT
        if word == 'building_level':
            return 1
        if isinstance(word, str) and word.startswith('eu5ab_'):
            self.work[word] += 1
        if isinstance(word, str) and ('goods_supply_in_market(' in word or
                                      'goods_demand_in_market(' in word or 'market_price(' in word or
                                      word.startswith('default_price(')):
            return 1
        if isinstance(word, str) and word.startswith('eu5ab_market_effective_demand_'):
            return 1
        if isinstance(word, str) and word.startswith('eu5ab_market_pending_known_'):
            return True
        return super().value(word, stack)

    def execute(self, entries, stack):
        for name, _, _ in entries:
            if name.startswith('eu5ab_'):
                self.work[name] += 1
        return super().execute(entries, stack)

    def capture(self, kind):
        self.scopes.update(eu5ab_candidate_building=kind, eu5ab_quote_ticket=1)
        self.vars['location'].update(eu5ab_quote_ticket=1, eu5ab_quote_country=self.ROOT,
                                    eu5ab_quote_month=7, eu5ab_quote_year=1436)
        self.lists['location'].setdefault('eu5ab_quote_requests', []).append(kind)
        self.lists[self.ROOT]['eu5ab_quote_pending_locations'] = ['location']
        self.stubs['eu5ab_dispatch_queue_bridge'] = lambda: None
        self.run('eu5ab_gui_capture_candidate_quote', 'location')


class QuoteScreeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = ScreeningVM()

    def vm(self):
        return deepcopy(self.template)

    def test_cheap_and_late_rejections_complete_without_ranking(self):
        cases = ('permission', 'cost', 'capacity', 'input', 'price', 'pending', 'metric', 'market',
                 *(gate for gate, _ in FOOD_BUILDING_FINAL_GATES))
        for reason in cases:
            with self.subTest(reason=reason):
                vm = self.vm()
                if reason == 'permission': vm.scopes['eu5ab_engine_can_build'] = False
                elif reason == 'cost': vm.scopes['eu5ab_engine_cost'] = 0
                elif reason == 'capacity': vm.vars['location']['eu5ab_capacity_factor'] = 0
                elif reason == 'market': vm.markets['location'] = None
                else:
                    gate = {'input': 'eu5ab_inputs_available', 'price': 'eu5ab_output_not_oversupplied',
                            'pending': 'eu5ab_candidate_pending_allowed',
                            'metric': 'eu5ab_engine_candidate_passes_selected_metric'}.get(reason, reason)
                    vm.native[gate] = False
                vm.vars['location'].update(eu5ab_pf_reference_building='stale',
                                          eu5ab_quote_production_type='stale',
                                          eu5ab_quote_production_output_ready=True)
                vm.variable_maps.setdefault('location', {})['eu5ab_quote_production_reference_output'] = {'goods:tools': 999}
                vm.capture('rejected')
                counters = dict(permission='vanilla', cost='engine_economics',
                    capacity='building_capacity', input='inputs', price='oversupply',
                    pending='pending_output', metric='engine_economics', market='vanilla')
                counter = dict(FOOD_BUILDING_FINAL_GATES).get(reason, 'eu5ab_diag_fail_' + counters.get(reason, ''))
                self.assertEqual(vm.vars[vm.ROOT].get(counter), 1)
                # A late duplicate receipt cannot count this rejection twice.
                vm.run('eu5ab_gui_capture_candidate_quote', 'location')
                self.assertEqual(vm.vars[vm.ROOT].get(counter), 1)
                self.assertEqual(vm.lists['location']['eu5ab_batch_screened_types'], ['rejected'])
                self.assertEqual(vm.lists['location']['eu5ab_quote_ready_types'], ['rejected'])
                self.assertFalse(vm.lists['location'].get('eu5ab_batch_passed_types'))
                self.assertFalse(vm.lists['location']['eu5ab_quote_requests'])
                self.assertFalse(vm.lists[vm.ROOT]['eu5ab_quote_pending_locations'])
                self.assertNotIn('eu5ab_pf_reference_building', vm.vars['location'])
                self.assertFalse(any(k.startswith('eu5ab_quote_production_') for k in vm.vars['location']))
                self.assertFalse(vm.variable_maps['location'].get('eu5ab_quote_production_reference_output'))
                for call in ('eu5ab_prepare_candidate_score_snapshot', 'eu5ab_batch_compute_quote_score',
                             'eu5ab_batch_snapshot_quote_quantities'):
                    self.assertEqual(vm.work[call], 0)
                if reason in ('permission', 'cost', 'capacity', 'market'):
                    self.assertEqual(vm.work['eu5ab_prepare_production_reference'], 0)
                    self.assertEqual(vm.work['eu5ab_engine_adjusted_profit'], 0)
                vm.scopes['eu5ab_engine_can_build'] = True
                vm.scopes['eu5ab_engine_cost'] = 100
                vm.vars['location']['eu5ab_capacity_factor'] = 1
                vm.markets['location'] = 'market'
                vm.native.update({name: True for name in (
                    'eu5ab_inputs_available', 'eu5ab_output_not_oversupplied',
                    'eu5ab_candidate_pending_allowed', 'eu5ab_engine_candidate_passes_selected_metric',
                    *(gate for gate, _ in FOOD_BUILDING_FINAL_GATES))})
                vm.capture('accepted')
                self.assertEqual(vm.lists['location']['eu5ab_batch_passed_types'], ['accepted'])
                self.assertEqual(vm.work['eu5ab_batch_compute_quote_score'], 1)
                self.assertFalse(vm.lists[vm.ROOT]['eu5ab_quote_pending_locations'])

    def test_emergency_outputless_and_capacity_exempt_candidates_keep_existing_rules(self):
        for reason in ('emergency', 'outputless', 'upgrade', 'special_capacity'):
            with self.subTest(reason=reason):
                vm = self.vm()
                if reason in ('emergency', 'outputless'):
                    vm.native['eu5ab_engine_candidate_passes_selected_metric'] = False
                    if reason == 'emergency': vm.native['eu5ab_engine_candidate_has_emergency_demand'] = True
                    else: vm.native['eu5ab_recipe_expected_output_value'] = 0
                else:
                    vm.vars['location']['eu5ab_capacity_factor'] = 0
                    if reason == 'upgrade':
                        vm.scopes['eu5ab_engine_replaced_building'] = 'old'
                        vm.native.update(building_level=1, building_can_be_upgraded_by=vm.ROOT)
                    else:
                        vm.native['employment_size'] = 0
                vm.capture('accepted')
                self.assertEqual(vm.lists['location']['eu5ab_batch_passed_types'], ['accepted'])

    def test_rejected_first_quote_still_initializes_month_and_market_ledgers(self):
        vm = self.vm()
        vm.vars[vm.ROOT].pop('eu5ab_batch_ledger_month')
        vm.lists[vm.ROOT]['eu5ab_batch_markets'] = []
        vm.scopes['eu5ab_engine_can_build'] = False
        vm.capture('rejected')
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_batch_ledger_month'], 7)
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_batch_markets'], ['market'])
        ledgers = deepcopy(vm.variable_maps[vm.ROOT])
        vm.capture('another_rejected')
        self.assertEqual(vm.variable_maps[vm.ROOT], ledgers)

    def test_all_rejected_quotes_let_the_batch_dispatcher_finish_remaining_phases(self):
        vm = self.vm()
        vm.vars[vm.ROOT].pop('eu5ab_bridge_rebuild', None)
        vm.lists[vm.ROOT]['eu5ab_q_phase_5_locations'] = ['location']
        vm.lists['location']['eu5ab_q_phase_5_types'] = ['first', 'last']
        vm.scopes['eu5ab_engine_can_build'] = False
        vm.capture('first')
        vm.capture('last')
        vm.run('eu5ab_dispatch_construction_batch', vm.ROOT)
        self.assertFalse(vm.lists[vm.ROOT]['eu5ab_quote_pending_locations'])
        self.assertNotIn('eu5ab_batch_waiting', vm.vars[vm.ROOT])
        self.assertNotIn('eu5ab_q_active', vm.vars[vm.ROOT])
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_phase'], 17)
        self.assertEqual(vm.commands, [])

    def test_opt_in_probe_counts_early_rejection_and_only_passed_ranking(self):
        vm = self.vm()
        vm.vars[vm.ROOT]['eu5ab_sp_enabled'] = True
        vm.stubs['eu5ab_probe_scan_quote'] = lambda: None
        vm.scopes['eu5ab_engine_can_build'] = False
        vm.capture('denied')
        vm.scopes['eu5ab_engine_can_build'] = True
        vm.capture('accepted')
        state = vm.vars[vm.ROOT]
        self.assertEqual(state['eu5ab_sp_screened'], 2)
        self.assertEqual(state['eu5ab_sp_screen_early_rejected'], 1)
        self.assertEqual(state['eu5ab_sp_screen_passed'], 1)
        self.assertEqual(state['eu5ab_sp_screen_score_calls'], 1)

    def test_adjusted_profit_zero_and_negative_results_are_read_once_and_cleared(self):
        vm = self.vm()
        f = generated_fixture()
        name = 'eu5ab_engine_adjusted_profit'
        vm.capacity_values[name] = parse(_blocks_for_token(f.values, '\n' + name + ' = ')[0])[0][2]
        vm.native.pop(name)
        name = 'eu5ab_prepare_quote_economy_snapshot'
        vm.stubs.pop(name)
        vm.definitions[name] = parse(_blocks_for_token(f.effects, '\n' + name + ' = ')[0])[0][2]
        for profit in map(Decimal, ('0', '-0.00001', '10.12345')):
            with self.subTest(profit=profit):
                vm.vars['location']['eu5ab_quote_production_type'] = 'accepted'
                vm.native['eu5ab_engine_adjusted_profit_live'] = profit
                vm.work.clear()
                vm.run(name, 'location')
                if profit == 0:
                    vm.vars['location'].pop('eu5ab_quote_production_adjusted_profit', None)
                vm.scopes['eu5ab_candidate_building'] = 'accepted'
                for _ in range(3):
                    self.assertEqual(vm.value('eu5ab_engine_adjusted_profit', ['location']), profit)
                self.assertEqual(vm.work['eu5ab_engine_adjusted_profit_live'], 1)
                vm.run('eu5ab_clear_quote_production_snapshot', 'location')
                self.assertEqual(vm.value('eu5ab_engine_adjusted_profit', ['location']), profit)
                self.assertEqual(vm.work['eu5ab_engine_adjusted_profit_live'], 2)


if __name__ == '__main__':
    unittest.main()
