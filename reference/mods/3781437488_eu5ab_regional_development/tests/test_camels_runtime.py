"""Camel integration through generated RGO scripts; native transactions are injected."""

from decimal import Decimal as D
import unittest

from tests._generated import generated_fixture
from tests._governor_script_vm import parse
from tests.test_rgo_batch_runtime import P, RgoBatchVM
from tests.test_rgo_decision_runtime import RgoDecisionVM


class CamelVM(RgoDecisionVM):
    def value(self, x, stack):
        # Keep the actual generated location/template score in this integration test.
        if x == 'eu5ab_location_need_score':
            return self.arithmetic(self.values[x], stack)
        if x in ('population', 'development', 'local_control', 'market_access',
                 'eu5ab_location_available_workforce_signal'):
            return D(0)
        # Native camel base price is 3; market quote 3.6 must mean 120%, not 360%.
        if x == 'default_price(goods:camels)':
            return D(3)
        if x == 'market.market_price(goods:camels)':
            return self.locations[stack[-1]]['price'] / 100 * 3
        return super().value(x, stack)


class CamelRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = generated_fixture()
        cls.effects = {k: v for k, _, v in parse(fixture.effects)}
        cls.triggers = {k: v for k, _, v in parse(fixture.triggers)}
        cls.values = {k: v for k, _, v in parse(fixture.values)}

    def vm(self):
        vm = CamelVM(self.effects, self.triggers, self.values)
        for location in ('a', 'b', 'c'):
            vm.locations[location].update(good='camels', method='farming', output_price=D(3))
        return vm

    def test_strategy_and_template_shortage_boundary_match_existing_policy(self):
        vm = self.vm()
        for demand, supply in ((0, 0), (100, 0), (100, '89.99999'), (100, 90), (100, 200)):
            vm.markets['m1'].update(demand=D(demand), supply=D(supply))
            for good, template_bonus in (('camels', 500), ('horses', 520)):
                vm.locations['a']['good'] = good
                military_score = vm.number('eu5ab_rgo_candidate_score')
                vm.locations['a']['good'] = 'silver'
                self.assertEqual(military_score - vm.number('eu5ab_rgo_candidate_score'), 180)
                vm.locations['a']['good'] = good
                for policy in (0, 5, 7):  # Unassigned, Frontier, Military Industry.
                    with self.subTest(good=good, demand=demand, supply=supply, policy=policy):
                        vm.vars['a']['eu5ab_policy_id'] = D(policy)
                        expected = template_bonus if policy and D(supply) < D(demand) * D('.9') else 0
                        self.assertEqual(vm.number('eu5ab_location_need_score'), expected)

    def test_native_price_and_farming_cost_category(self):
        vm = self.vm()
        vm.locations['a']['price'] = D(120)
        self.assertEqual(vm.number('eu5ab_rgo_price_percent'), 120)
        self.assertEqual(vm.estimate(), 125)
        vm.modifiers['farming'] = D('-.2')
        vm.modifiers['mining'] = D('-.9')
        self.assertEqual(vm.estimate(), 100)

    def test_strategic_and_template_scores_do_not_bypass_admission(self):
        for reason in ('allowed', 'price', 'staffing', 'forecast', 'pending', 'cash', 'budget'):
            with self.subTest(reason=reason):
                vm = self.vm()
                vm.vars['a']['eu5ab_policy_id'] = D(7)
                vm.markets['m1'].update(demand=D(100), supply=D(50), stock=D(0), exhaustion=True)
                if reason == 'price':
                    vm.locations['a']['price'] = D(80)
                elif reason == 'staffing':
                    vm.locations['a']['workers'] = D('3.99999')
                elif reason == 'forecast':
                    vm.vars['country'].update(eu5ab_global_rgo_workforce_mode=D(2),
                                              eu5ab_global_rgo_job_fill_deadline_months=D(0))
                    vm.locations['a']['idle'] = D(0)
                elif reason == 'pending':
                    vm.maps['country']['eu5ab_rgo_pending_output_camels'] = {'m1': D(60)}
                elif reason == 'cash':
                    vm.gold = D('324.99999')
                elif reason == 'budget':
                    vm.vars['country']['eu5ab_global_budget_remaining'] = D(0)
                self.assertGreater(vm.number('eu5ab_rgo_base_score'), 0)
                self.assertFalse(vm.allowed('eu5ab_rgo_food_emergency_enabled'))
                self.assertEqual(vm.allowed('eu5ab_rgo_expansion_allowed'), reason == 'allowed')

    def test_camel_batch_failure_releases_holds_without_blocking_horses(self):
        vm = RgoBatchVM()
        vm.candidate('failed', good='camels', base=100, output=8, demand=10, supply=10)
        vm.candidate('camel', good='camels', base=99, output=8, demand=10, supply=10)
        vm.candidate('horse', good='horses', base=50, output=8, demand=10, supply=10)
        vm.failures.add('failed')
        vm.run('eu5ab_dispatch_construction_batch', vm.ROOT)
        self.assertEqual([c[1] for c in vm.commands], ['failed', 'horse', 'camel'])
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_global_budget_spent'], 20)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_batch_reserved'], 0)
        self.assertEqual(vm.vars['failed']['eu5ab_batch_slots'], 3)
        self.assertNotIn('eu5ab_rgo_pending_levels', vm.vars['failed'])
        for good, location in (('camels', 'camel'), ('horses', 'horse')):
            self.assertEqual(vm.variable_maps[vm.ROOT][P + 'held_' + good]['market'], 0)
            self.assertEqual(vm.vars[location]['eu5ab_rgo_pending_good'], 'goods:' + good)
            self.assertEqual(vm.vars[location]['eu5ab_rgo_pending_quantity'], 8)

    def test_pending_release_is_per_good_and_waits_for_staffed_completion(self):
        vm = self.vm()
        vm.locations['b']['good'] = 'horses'
        vm.attempt('a')
        vm.attempt('b')
        for location in ('a', 'b'):
            self.assertEqual(vm.number('eu5ab_rgo_market_pending_quantity', location), D('1.5'))
        vm.locations['a']['queue'] = D(0)  # Camel construction cancelled.
        vm.refresh()
        self.assertEqual(vm.number('eu5ab_rgo_market_pending_quantity', 'a'), 0)
        self.assertEqual(vm.number('eu5ab_rgo_market_pending_quantity', 'b'), D('1.5'))
        vm.attempt('c')
        vm.locations['c'].update(queue=D(0), levels=D(5), workers=D('4.9'))
        vm.refresh()
        self.assertEqual(vm.number('eu5ab_rgo_market_pending_quantity', 'a'), D('1.5'))
        vm.locations['c']['workers'] = D(5)
        vm.refresh()
        self.assertEqual(vm.number('eu5ab_rgo_market_pending_quantity', 'a'), 0)
        self.assertEqual(vm.number('eu5ab_rgo_market_pending_quantity', 'b'), D('1.5'))


if __name__ == '__main__':
    unittest.main()
