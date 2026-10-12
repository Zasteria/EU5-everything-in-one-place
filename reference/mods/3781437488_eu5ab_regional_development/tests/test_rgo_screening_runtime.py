"""Execute RGO screening arithmetic, branch order and snapshot lifetime.

Native market facts are injected; operation counts are not game timings.
"""
from collections import Counter
from decimal import Decimal as D
import unittest

from src.eu5autobuild.rgo_screening import PREFIX, VALUES, field
from tests._generated import generated_fixture
from tests._governor_script_vm import parse
from tests.test_rgo_decision_runtime import RgoDecisionVM


class ScreeningVM(RgoDecisionVM):
    def __init__(self, effects, triggers, values):
        self.reads = Counter()
        self.blocked = None
        self.staged = []
        super().__init__(effects, triggers, values)

    def value(self, value, stack):
        if isinstance(value, str) and value.endswith('_screen_live'):
            self.reads[value] += 1
        return super().value(value, stack)

    def test(self, key, op, value, stack):
        if key == self.blocked:
            return value == 'no'
        return super().test(key, op, value, stack)

    def execute(self, entries, stack):
        index = 0
        while index < len(entries):
            key, _, body = entries[index]
            end = index + 1
            if key == 'if':
                while end < len(entries) and entries[end][0] in ('else_if', 'else'):
                    end += 1
            if key == 'eu5ab_stage_rgo_candidate':
                # Staging publishes a candidate, never mutates market ledgers.
                self.staged.append(stack[-1])
            else:
                super().execute(entries[index:end], stack)
            if key == 'set_variable' and isinstance(body, list):
                name = dict((k, v) for k, _, v in body)['name']
                if name.startswith(PREFIX) and self.vars[stack[-1]].get(name) == 0:
                    self.vars[stack[-1]].pop(name, None)
            index = end


class RgoScreeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = generated_fixture()
        cls.effects = {k: v for k, _, v in parse(fixture.effects)}
        cls.triggers = {k: v for k, _, v in parse(fixture.triggers)}
        cls.values = {k: v for k, _, v in parse(fixture.values)}
        router = cls.effects['eu5ab_try_construct_policy_candidate']
        start = next(i for i, (k, _, v) in enumerate(router) if k == 'change_variable'
                     and ('name', '=', 'eu5ab_worker_eu5ab_diag_rgo_checked') in v)
        # The RGO if/else chain ends before the deferred building cooldown.
        end = start + 1
        while router[end][0] in ('if', 'else_if', 'else'):
            if end > start + 1 and router[end][0] == 'if':
                break
            end += 1
        cls.router = router[start:end]

    def vm(self):
        return ScreeningVM(self.effects, self.triggers, self.values)

    def prepare(self, vm, location='a'):
        vm.execute(vm.definitions['eu5ab_prepare_rgo_screening'], [location])

    def clear(self, vm, location='a'):
        vm.execute(vm.definitions['eu5ab_clear_rgo_screening'], [location])

    def observation(self, vm, location='a'):
        numbers = (*VALUES, 'eu5ab_rgo_pending_factor', 'eu5ab_rgo_price_factor',
                   'eu5ab_rgo_base_score', 'eu5ab_rgo_queue_order_score')
        return ([vm.number(n, location) for n in numbers],
                [vm.allowed(n, location) for n in ('eu5ab_rgo_pending_data_available',
                 'eu5ab_rgo_pending_allowed', 'eu5ab_rgo_market_need_present')])

    def test_market_boundaries_unknown_emergency_zero_and_native_read_counts(self):
        for demand, supply, pending, unknown, price, emergency in (
            (100, 95, 3, 0, 90, False), (0, 0, 0, 0, 0, False),
            (100, 200, 10, 0, 100, False), (100, 100, '9.99999', 0, 80, False),
            (100, 100, 0, 1, 150, False), (-1, 0, 0, 0, 0, False),
            (100, -1, 0, 0, -1, False), (100, 200, 100, 1, 50, True),
        ):
            vm = self.vm()
            good = 'fish' if emergency else 'iron'
            vm.locations['a'].update(good=good, price=D(price))
            vm.markets['m1'].update(demand=D(demand), supply=D(supply), exhaustion=emergency)
            vm.maps['country']['eu5ab_rgo_pending_output_' + good] = {'m1': D(pending)}
            vm.maps['country']['eu5ab_rgo_pending_unknown_' + good] = {'m1': D(unknown)}
            expected = self.observation(vm)
            vm.reads.clear()
            self.prepare(vm)
            before = vm.reads.copy()
            for _ in range(3):
                self.assertEqual(self.observation(vm), expected)
            self.assertEqual(vm.reads, before)
            self.assertEqual(before, Counter({n + '_screen_live': 1 for n in VALUES}))
            for name, value in zip(VALUES, expected[0]):
                if value == 0:
                    self.assertNotIn(field(name), vm.vars['a'])
                    self.assertIn(field(name) + '_ready', vm.vars['a'])
            self.clear(vm)
            self.assertEqual(self.observation(vm), expected)
            self.assertFalse(any(k.startswith(PREFIX) for k in vm.vars['a']))

    def test_location_isolation_refresh_and_live_fallback(self):
        vm = self.vm()
        self.prepare(vm)
        original = vm.number('eu5ab_rgo_market_demand')
        vm.markets['m1']['demand'] = D(333)
        self.assertEqual(vm.number('eu5ab_rgo_market_demand'), original)
        self.assertEqual(vm.number('eu5ab_rgo_market_demand', 'b'), 333)
        self.prepare(vm, 'b')
        self.clear(vm)
        self.assertEqual(vm.number('eu5ab_rgo_market_demand'), 333)
        vm.markets['m1']['demand'] = D(444)
        self.prepare(vm, 'b')
        self.assertEqual(vm.number('eu5ab_rgo_market_demand', 'b'), 444)

    def test_base_score_threshold_zero_omission_and_live_read_after_clear(self):
        for target in (-1, 0, 1):
            vm = self.vm()
            vm.locations['a']['need'] += D(target) - vm.number('eu5ab_rgo_base_score')
            self.prepare(vm)
            before = vm.reads['eu5ab_rgo_base_score_screen_live']
            for _ in range(3):
                self.assertEqual(vm.number('eu5ab_rgo_base_score'), target)
                self.assertEqual(vm.allowed('eu5ab_rgo_score_allowed'), target >= 0)
                vm.number('eu5ab_rgo_queue_order_score')
            self.assertEqual(vm.reads['eu5ab_rgo_base_score_screen_live'], before)
            if target == 0:
                self.assertNotIn(field('eu5ab_rgo_base_score'), vm.vars['a'])
                self.assertIn(field('eu5ab_rgo_base_score') + '_ready', vm.vars['a'])
            vm.locations['a']['need'] += 300
            self.assertEqual(vm.number('eu5ab_rgo_base_score'), target)
            self.clear(vm)
            self.assertEqual(vm.number('eu5ab_rgo_base_score'), target + 300)

    def test_router_preserves_all_rejection_reasons_diagnostics_and_clears_before_return(self):
        gates = ('capacity_available', 'location_available', 'enabled', 'finance_available',
                 'utilization_allowed', 'workforce_allowed', 'pending_data_available',
                 'market_need_present', 'score_allowed', 'pending_allowed')
        for gate in (None, *gates):
            cached, live = self.vm(), self.vm()
            # Disable only preparation in the reference: all actual gates,
            # arithmetic and published diagnostic writes still execute.
            live.definitions = {**live.definitions, 'eu5ab_prepare_rgo_screening': []}
            for vm in (cached, live):
                vm.blocked = 'eu5ab_rgo_' + gate if gate else None
                vm.locations['a']['price'] = D(150)
                vm.markets['m1']['supply'] = D(50)
                # Counter initialization belongs to the outer location worker.
                def initialize(entries):
                    for k, _, v in entries:
                        if k == 'change_variable':
                            vm.vars['a'].setdefault(dict((a, c) for a, _, c in v)['name'], D(0))
                        elif isinstance(v, list):
                            initialize(v)
                initialize(self.router)
                vm.reads.clear()
                vm.execute(self.router, ['a'])
            with self.subTest(gate=gate):
                self.assertEqual(cached.vars, live.vars)
                self.assertEqual(cached.staged, live.staged)
                self.assertFalse(any(k.startswith(PREFIX) for k in cached.vars['a']))
                if gate in gates[:6]:
                    self.assertFalse(cached.reads)


if __name__ == '__main__':
    unittest.main()
