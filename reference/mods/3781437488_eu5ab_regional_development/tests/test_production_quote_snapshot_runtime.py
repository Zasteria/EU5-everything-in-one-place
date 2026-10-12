"""Quote-local validation preserves live quantities and never outlives a quote."""
from collections import Counter
from copy import deepcopy
from decimal import Decimal, ROUND_DOWN
import unittest

from src.eu5autobuild.production_goods import goods_in
from tests._generated import generated_fixture, _blocks_for_token
from tests._governor_script_vm import parse
from tests.test_engine import RULES
from tests.test_production_reference import ReferenceSearchVM


class QuoteProductionVM(ReferenceSearchVM):
    def __init__(self):
        super().__init__()
        self.checks = Counter()
        self.efficiency_reads = 0
        self.estates = set()
        self.quantity_reads = 0
        name = 'eu5ab_batch_snapshot_quote_quantities'
        self.definitions[name] = parse(_blocks_for_token(
            generated_fixture().effects, '\n' + name + ' = ')[0])[0][2]
        # Include construction_batch's monthly-quote wrapper around the trigger.
        name = 'eu5ab_pending_identity_known'
        self.capacity_triggers[name] = parse(_blocks_for_token(
            generated_fixture().triggers, '\n' + name + ' = ')[0])[0][2]

    def test(self, key, operator, value, stack):
        if key in ('eu5ab_pending_identity_known_live', 'eu5ab_pending_exact_predecessor_live',
                   'eu5ab_pr_recipe_known', 'eu5ab_pr_efficiency_known', 'any_production_method_of_building'):
            self.checks[key] += 1
        return super().test(key, operator, value, stack)

    def value(self, expression, stack):
        if isinstance(expression, str):
            if expression.startswith(('eu5ab_candidate_net_', 'eu5ab_candidate_old_')):
                self.quantity_reads += 1
            if expression == 'estate_type':
                return 'estate:nobles' if stack[-1] in self.estates else None
            if 'building_efficiency(building_type:' in expression:
                self.efficiency_reads += 1
        return super().value(expression, stack)

    def prepare(self):
        self.run('eu5ab_prepare_quote_production_snapshot', 'location')
        self.run('eu5ab_prepare_quote_production_output_quantities', 'location')
        self.run('eu5ab_prepare_quote_production_input_quantities', 'location')

    def clear(self):
        self.run('eu5ab_clear_quote_production_snapshot', 'location')

    def quantities(self):
        return {f'{kind}_{good}': self.value(f'eu5ab_candidate_{kind}_{good}',
                                           [self.scopes['eu5ab_candidate_building']])
                for good in goods_in(self.models, RULES)
                for kind in ('net_output', 'net_input', 'old_output', 'old_input')}

    def upgrade(self):
        self.building_types['old'] = self.building_types['foundry']
        self.active_methods['old'] = list(self.active_methods['foundry'])
        self.building_locations['old'] = 'location'
        self.vars['old'], self.lists['old'] = {}, {}
        self.facts['old'] = dict(building_level=3, building_can_be_upgraded_by=self.ROOT)
        self.scopes['eu5ab_engine_replaced_building'] = 'old'
        self.scopes['eu5ab_candidate_building'] = self.building_types['foundry'] = 'building_type:iron_mill'
        self.active_methods['foundry'] = ['production_method:' + slot[0].production_method_id
                                         for slot in self.models['iron_mill'].slots]


class QuoteProductionSnapshotTests(unittest.TestCase):
    def test_new_build_reuses_market_donor_validation_and_its_own_efficiency(self):
        vm = QuoteProductionVM()
        vm.add_reference('second', 'donor')
        vm.facts['foundry']['building_level'] = 0
        vm.vars['location']['eu5ab_quote_production_active'] = True
        vm.run('eu5ab_prepare_production_reference', 'location')
        self.assertEqual(vm.visited, ['location', 'second'])
        self.assertEqual(vm.vars['location']['eu5ab_pf_reference_building'], 'donor')
        vm.prepare()
        self.assertEqual(vm.checks['eu5ab_pending_identity_known_live'], 0)
        self.assertEqual(vm.efficiency_reads, 1)
        self.assertEqual(vm.value('eu5ab_candidate_net_output_tools', [vm.scopes['eu5ab_candidate_building']]), 4)
        self.assertEqual(vm.value('eu5ab_candidate_old_output_tools', [vm.scopes['eu5ab_candidate_building']]), 0)

    def test_quantity_caches_keep_fixed_point_multiplication_and_old_output_subtraction(self):
        class FixedVM(QuoteProductionVM):
            def value(self, word, stack):
                result = super().value(word, stack)
                return Decimal(str(result)) if isinstance(result, (int, float, Decimal)) and not isinstance(result, bool) else result

            def normalize_arithmetic(self, value):
                return Decimal(str(value)).quantize(Decimal('0.00001'), rounding=ROUND_DOWN)

        template = FixedVM()
        fields = ('net_output_tools', 'net_input_iron', 'old_output_tools', 'old_input_iron')
        for upgrade in (False, True):
            for efficiency in map(Decimal, ('0', '0.00001', '0.12345', '5', '7.00001')):
                with self.subTest(upgrade=upgrade, efficiency=efficiency):
                    vm = deepcopy(template)
                    if upgrade:
                        vm.upgrade()
                    vm.efficiencies['location'] = efficiency
                    kind = vm.scopes['eu5ab_candidate_building']
                    expected = {f: vm.value('eu5ab_candidate_' + f, [kind]) for f in fields}
                    vm.prepare()
                    prepared = vm.checks.copy(), vm.efficiency_reads
                    self.assertEqual({f: vm.value('eu5ab_candidate_' + f, [kind]) for f in fields}, expected)
                    self.assertEqual((vm.checks, vm.efficiency_reads), prepared)

    def test_search_validation_is_carried_only_inside_the_current_quote(self):
        vm = QuoteProductionVM()
        vm.vars['location']['eu5ab_quote_production_active'] = True
        vm.run('eu5ab_prepare_production_reference', 'location')
        validated = vm.checks.copy()
        vm.prepare()
        self.assertEqual(vm.checks['eu5ab_pending_identity_known_live'], 0)
        self.assertEqual(vm.checks['eu5ab_pr_recipe_known'], validated['eu5ab_pr_recipe_known'])
        self.assertEqual(vm.checks['eu5ab_pr_efficiency_known'], validated['eu5ab_pr_efficiency_known'])
        self.assertEqual(vm.efficiency_reads, 1)
        prepared = vm.checks.copy(), vm.efficiency_reads
        vm.quantities()
        vm.run('eu5ab_batch_snapshot_quote_quantities', 'location')
        self.assertEqual((vm.checks, vm.efficiency_reads), prepared)
        vm.clear()
        vm.active_methods['foundry'] = ['production_method:unknown']
        vm.vars['location']['eu5ab_quote_production_active'] = True
        vm.run('eu5ab_prepare_production_reference', 'location')
        self.assertNotIn('eu5ab_pf_reference_building', vm.vars['location'])
        vm.prepare()
        self.assertFalse(any(vm.quantities().values()))
        self.assertEqual(vm.checks['eu5ab_pending_identity_known_live'], 0)
        vm.clear()
        vm.run('eu5ab_prepare_production_reference', 'location')
        self.assertNotIn('eu5ab_quote_production_search_type', vm.vars['location'])

    def test_sparse_maps_match_all_live_goods_and_clear_legacy_candidate_only(self):
        for mode in ('new', 'replacement', 'missing_reference', 'unknown_method', 'zero'):
            with self.subTest(mode=mode):
                vm = QuoteProductionVM()
                if mode in ('replacement', 'missing_reference'):
                    vm.building_types['old'] = 'building_type:tools_guild'
                    vm.active_methods['old'] = ['production_method:bronze_tools_guild_maintenance']
                    vm.building_locations['old'] = 'location'
                    vm.facts['old'] = dict(building_level=2, building_can_be_upgraded_by=vm.ROOT)
                    vm.scopes['eu5ab_engine_replaced_building'] = 'old'
                if mode == 'missing_reference':
                    vm.vars['location'].pop('eu5ab_pf_reference_building')
                elif mode == 'unknown_method':
                    vm.active_methods['foundry'] = ['production_method:unknown']
                elif mode == 'zero':
                    vm.efficiencies['location'] = 0
                expected = vm.quantities()
                candidate = vm.scopes['eu5ab_candidate_building']
                for field in expected:
                    vm.variable_maps.setdefault('location', {})['eu5ab_quote_' + field] = {
                        candidate: 999, 'another_candidate': 17}
                vm.prepare()
                vm.quantity_reads = 0
                vm.run('eu5ab_batch_snapshot_quote_quantities', 'location')
                actual = {field: vm.variable_maps['location'].get('eu5ab_quote_' + field, {}).get(candidate, 0)
                          for field in expected}
                self.assertEqual(actual, expected)
                self.assertLess(vm.quantity_reads, len(expected) // 4)
                for field in expected:
                    self.assertEqual(vm.variable_maps['location']['eu5ab_quote_' + field]['another_candidate'], 17)
                if mode in ('replacement', 'missing_reference'):
                    self.assertGreater(actual['old_input_copper'], 0)
                    self.assertGreater(actual['old_input_tin'], 0)
                vm.clear()
                # A subsequent quote has lost the predecessor and uses another
                # active reference method; no old-only quantity may survive.
                vm.scopes.pop('eu5ab_engine_replaced_building', None)
                vm.active_methods['foundry'] = ['production_method:unknown']
                expected = vm.quantities()
                vm.prepare()
                vm.run('eu5ab_batch_snapshot_quote_quantities', 'location')
                self.assertEqual({field: vm.variable_maps['location'].get('eu5ab_quote_' + field, {}).get(candidate, 0)
                                  for field in expected}, expected)

    def test_all_goods_match_live_and_validation_cost_does_not_grow_with_reads(self):
        for upgrade in (False, True):
            with self.subTest(upgrade=upgrade):
                vm = QuoteProductionVM()
                if upgrade:
                    vm.upgrade()
                vm.efficiencies['location'] = 5
                expected = vm.quantities()
                live_checks, live_reads = sum(vm.checks.values()), vm.efficiency_reads
                vm.checks.clear()
                vm.efficiency_reads = 0
                vm.prepare()
                prepared = (deepcopy(vm.checks), vm.efficiency_reads)
                for _ in range(2):
                    self.assertEqual(vm.quantities(), expected)
                self.assertEqual((vm.checks, vm.efficiency_reads), prepared)
                self.assertEqual(vm.checks['eu5ab_pending_identity_known_live'], 1)
                self.assertEqual(vm.checks['eu5ab_pending_exact_predecessor_live'], 1)
                self.assertLess(sum(vm.checks.values()), live_checks)
                self.assertLess(vm.efficiency_reads, live_reads)
                vm.clear()
                self.assertFalse(any(k.startswith('eu5ab_quote_production_') for k in vm.vars['location']))

    def test_unknown_invalid_and_zero_efficiency_references_keep_live_results(self):
        template = QuoteProductionVM()
        for failure in ('absent', 'foreign', 'estate', 'unknown_method', 'ambiguous', 'negative', 'zero'):
            with self.subTest(failure=failure):
                vm = deepcopy(template)
                if failure == 'absent':
                    vm.vars['location'].pop('eu5ab_pf_reference_building')
                elif failure == 'foreign':
                    vm.building_locations['foundry'] = 'second'
                    vm.owners['second'] = 'foreign'
                elif failure == 'estate':
                    vm.estates.add('foundry')
                elif failure in ('unknown_method', 'ambiguous'):
                    vm.building_types['foundry'] = vm.scopes['eu5ab_candidate_building'] = 'building_type:mason'
                    vm.active_methods['foundry'] = (['production_method:unknown'] if failure == 'unknown_method'
                        else ['production_method:' + m.production_method_id for m in vm.models['mason'].slots[0]])
                else:
                    vm.efficiencies['location'] = -1 if failure == 'negative' else 0
                expected = vm.quantities()
                vm.prepare()
                if failure == 'zero':
                    vm.vars['location'].pop('eu5ab_quote_production_reference_efficiency', None)
                prepared = deepcopy(vm.checks)
                self.assertEqual(vm.quantities(), expected)
                self.assertEqual(vm.checks, prepared)
                self.assertEqual('eu5ab_quote_production_reference_known' in vm.vars['location'], failure == 'zero')
                self.assertFalse(any(expected.values()))

    def test_predecessor_rejection_caches_false_instead_of_reusing_a_previous_success(self):
        vm = QuoteProductionVM()
        vm.upgrade()
        vm.prepare()
        self.assertIn('eu5ab_quote_production_predecessor_known', vm.vars['location'])
        for failure in ('captured_absence', 'foreign_location', 'no_upgrade', 'unknown_recipe'):
            with self.subTest(failure=failure):
                case = deepcopy(vm)
                case.clear()
                if failure == 'captured_absence':
                    case.vars['location']['eu5ab_quote_no_replacement'] = True
                elif failure == 'foreign_location':
                    case.building_locations['old'] = 'second'
                elif failure == 'no_upgrade':
                    case.facts['old']['building_can_be_upgraded_by'] = 'foreign'
                else:
                    case.active_methods['old'] = ['production_method:unknown']
                expected = case.quantities()
                case.prepare()
                self.assertNotIn('eu5ab_quote_production_predecessor_known', case.vars['location'])
                self.assertEqual(case.quantities(), expected)
                self.assertEqual(expected['old_output_tools'], 0)

    def test_next_quote_and_different_type_cannot_reuse_an_earlier_result(self):
        vm = QuoteProductionVM()
        vm.prepare()
        vm.scopes['eu5ab_candidate_building'] = 'building_type:mason'
        self.assertFalse(vm.test('eu5ab_quote_production_current', '=', 'yes', ['building_type:mason']))
        self.assertFalse(any(vm.quantities().values()))
        vm.scopes['eu5ab_candidate_building'] = 'building_type:iron_foundry'
        vm.clear()
        # A later callback, including one after loading a save, starts empty.
        vm = deepcopy(vm)
        vm.day = 3
        vm.efficiencies['location'] = 7
        expected = vm.quantities()
        vm.prepare()
        self.assertEqual(vm.quantities(), expected)
        self.assertEqual(expected['net_output_tools'], 14)
        vm.active_methods['foundry'] = ['production_method:unknown']
        vm.prepare()
        self.assertNotIn('eu5ab_quote_production_reference_known', vm.vars['location'])
        self.assertFalse(any(vm.quantities().values()))

    def test_screening_brackets_every_candidate_and_skipped_market_with_cleanup(self):
        screen = parse(_blocks_for_token(generated_fixture().effects, '\neu5ab_batch_screen_quote = ')[0])[0][2]
        clear = 'eu5ab_clear_quote_production_snapshot'
        keys = [key for key, _, _ in screen]
        self.assertLess(keys.index(clear), keys.index('owner'))
        self.assertLess(max(i for i, key in enumerate(keys) if key == clear),
                        keys.index('add_to_variable_list'))
        text = _blocks_for_token(generated_fixture().effects, '\neu5ab_batch_screen_quote = ')[0]
        self.assertLess(text.index('eu5ab_prepare_production_reference = yes'),
                        text.index('eu5ab_prepare_quote_production_snapshot = yes'))
        self.assertLess(text.index('eu5ab_prepare_quote_production_snapshot = yes'),
                        text.index('eu5ab_prepare_candidate_score_snapshot = yes'))


if __name__ == '__main__':
    unittest.main()
