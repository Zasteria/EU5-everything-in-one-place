"""Sparse pending-output checks must preserve the full-goods calculation."""
import unittest

from tests import test_market_supply_runtime as supply_fixture
from tests._governor_script_vm import parse


class PendingGoodsVM(supply_fixture.SupplyVM):
    def __init__(self):
        super().__init__()
        self.output = {}
        self.old_output = {}
        self.pending_factors = {}
        self.unknown_goods = set()
        self.identity_known = True
        self.output_reads = []

    def value(self, value, stack):
        if isinstance(value, str):
            prefix = 'eu5ab_candidate_net_output_'
            if value.startswith(prefix):
                good = value[len(prefix):]
                self.output_reads.append(good)
                return max(0, self.output.get(good, 0) - self.old_output.get(good, 0))
            prefix = 'eu5ab_market_pending_factor_'
            if value.startswith(prefix):
                return self.pending_factors.get(value[len(prefix):], 1)
        return super().value(value, stack)

    def test(self, key, operator, value, stack):
        if key == 'eu5ab_pending_identity_known':
            return self.identity_known == (value == 'yes')
        prefix = 'eu5ab_market_pending_known_'
        if key.startswith(prefix):
            return (key[len(prefix):] not in self.unknown_goods) == (value == 'yes')
        return super().test(key, operator, value, stack)


def legacy_definitions(goods):
    known = ' '.join(f'OR = {{ eu5ab_candidate_net_output_{g} <= 0 eu5ab_market_pending_known_{g} = yes }}' for g in goods)
    checks = ' '.join(f'OR = {{ eu5ab_candidate_net_output_{g} <= 0 eu5ab_market_pending_factor_{g} > 0 }}' for g in goods)
    triggers = f'''eu5ab_candidate_pending_data_ready = {{ {known} }}
eu5ab_candidate_pending_allowed = {{
    eu5ab_candidate_production_cooldown_clear = yes
    eu5ab_candidate_pending_data_ready = yes
    OR = {{
        NOT = {{ eu5ab_candidate_has_direct_output = yes }}
        NOT = {{ eu5ab_pending_identity_known = yes }}
        AND = {{ scope:eu5ab_candidate_location = {{ exists = market }} OR = {{
            AND = {{ scope:eu5ab_candidate_location = {{ eu5ab_food_emergency_enabled = yes }} eu5ab_candidate_produces_food = yes }}
            AND = {{ {checks} }}
        }} }}
    }}
}}'''
    values = []
    for name, weighted in (('weight', False), ('weighted', True)):
        terms = ' '.join(
            f'if = {{ limit = {{ eu5ab_candidate_net_output_{g} > 0 }} add = {{ value = eu5ab_candidate_net_output_{g} multiply = "default_price(goods:{g})"' +
            (f' multiply = eu5ab_market_pending_factor_{g}' if weighted else '') + ' } }'
            for g in goods)
        values.append(f'eu5ab_pending_{name} = {{ value = 0 {terms} }}')
    return ({k: v for k, _, v in parse(triggers)},
            {k: v for k, _, v in parse('\n'.join(values))})


class PendingGoodsRuntimeTests(unittest.TestCase):
    def compare(self, vm, target):
        stack = ['building_type:' + target]
        all_goods = sorted({g for model in vm.models.values()
                            for slot in model.slots for method in slot for g in method.outputs})
        old_triggers, old_values = legacy_definitions(all_goods)

        def results():
            return (vm.test('eu5ab_candidate_pending_data_ready', '=', 'yes', stack),
                    vm.test('eu5ab_candidate_pending_allowed', '=', 'yes', stack),
                    vm.value('eu5ab_pending_weight', stack),
                    vm.value('eu5ab_pending_weighted', stack))

        vm.output_reads.clear()
        sparse = results()
        sparse_reads = list(vm.output_reads)
        vm.capacity_triggers.update(old_triggers)
        vm.capacity_values.update(old_values)
        vm.output_reads.clear()
        legacy = results()
        self.assertEqual(sparse, legacy)
        return sparse, sparse_reads, vm.output_reads

    def test_every_target_type_matches_full_goods_checks_and_weights(self):
        vm = PendingGoodsVM()
        for target, model in vm.models.items():
            goods = {g for slot in model.slots for method in slot for g in method.outputs}
            with self.subTest(target=target):
                # Restore generated definitions after each legacy comparison.
                _, triggers, values = supply_fixture.supply_scripts()
                vm.capacity_triggers.update(triggers)
                vm.capacity_values.update(values)
                vm.output = {g: 10 for g in goods}
                vm.pending_factors = {g: 0.3 for g in goods}
                _, reads, _ = self.compare(vm, target)
                self.assertTrue(set(reads) <= goods)

    def test_single_output_target_avoids_unrelated_recipe_reads(self):
        vm = PendingGoodsVM()
        vm.output = {'tools': 10}
        result, sparse, legacy = self.compare(vm, 'iron_foundry')
        self.assertEqual(result, (True, True, 10, 10))
        self.assertEqual(set(sparse), {'tools'})
        self.assertGreater(len(legacy), len(sparse) * 10)

    def test_unknown_data_zero_output_and_saturated_market_are_preserved(self):
        for quantity, unknown, factor in ((10, True, 1), (0, True, 0), (10, False, 0)):
            with self.subTest(quantity=quantity, unknown=unknown, factor=factor):
                vm = PendingGoodsVM()
                vm.output = {'tools': quantity}
                vm.unknown_goods = {'tools'} if unknown else set()
                vm.pending_factors = {'tools': factor}
                self.compare(vm, 'iron_foundry')

    def test_upgrade_subtracts_predecessor_and_food_emergency_keeps_override(self):
        for emergency in (False, True):
            vm = PendingGoodsVM()
            vm.output = {'tools': 10}
            vm.old_output = {'tools': 4, 'iron': 99}
            vm.pending_factors = {'tools': 0}
            vm.native['eu5ab_food_emergency_enabled'] = emergency
            vm.native['eu5ab_candidate_produces_food'] = emergency
            result, _, _ = self.compare(vm, 'iron_foundry')
            self.assertEqual(result[1], emergency)
            self.assertEqual(result[2], 6)

    def test_unknown_identity_and_unsupported_target_keep_zero_fallback(self):
        vm = PendingGoodsVM()
        vm.identity_known = False
        result, _, _ = self.compare(vm, 'iron_foundry')
        self.assertEqual(result, (True, True, 0, 0))
        vm = PendingGoodsVM()
        result, sparse, _ = self.compare(vm, 'unsupported_type')
        self.assertEqual(result, (True, True, 0, 0))
        self.assertEqual(sparse, [])


if __name__ == '__main__':
    unittest.main()
