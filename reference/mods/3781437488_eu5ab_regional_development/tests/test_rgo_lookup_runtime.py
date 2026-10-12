"""Compare the sparse raw-material dispatch with the former full traversal.

Native readings are injected; this measures executed predicates, not native
wall-clock time. All ledgers, including legacy unknown markers, stay active.
"""
from decimal import Decimal as D
import unittest

from src.eu5autobuild.rgo_automation import raw_goods
from tests import _generated as automation
from tests._governor_script_vm import parse
from tests.test_rgo_decision_runtime import RgoDecisionVM


def legacy_values():
    """Independent full-traversal baseline for the five changed lookups."""
    values = []
    for name, query in (('demand', 'goods_demand_in_market'),
                        ('supply', 'goods_supply_in_market')):
        body = [f'value = -1 if = {{ limit = {{ exists = market exists = raw_material }}']
        for good in raw_goods():
            body.append(f'if = {{ limit = {{ raw_material = goods:{good} }} '
                        f'value = "market.{query}(goods:{good})" }}')
        if name == 'demand':
            for good in raw_goods():
                body.append(f'if = {{ limit = {{ raw_material = goods:{good} owner = {{ '
                            f'is_key_in_variable_map = {{ name = eu5ab_build_future_input_{good} target = prev.market }} }} }} '
                            f'owner = {{ add = "variable_map(eu5ab_build_future_input_{good}|prev.market)" }} }}')
        values.append(f'eu5ab_legacy_rgo_market_{name} = {{ ' + ' '.join(body) + ' } }')
    for name, prefixes in (
        ('quantity', ('eu5ab_rgo_pending_output_', 'eu5ab_build_pending_')),
        ('unknown', ('eu5ab_rgo_pending_unknown_', 'eu5ab_build_pending_unknown_',
                     'eu5ab_build_future_input_unknown_')),
    ):
        body = ['value = 0 if = { limit = { exists = owner exists = market exists = raw_material }']
        for good in raw_goods():
            for prefix in prefixes:
                mapping = prefix + good
                body.append(f'if = {{ limit = {{ raw_material = goods:{good} owner = {{ '
                            f'is_key_in_variable_map = {{ name = {mapping} target = prev.market }} }} }} '
                            f'owner = {{ add = "variable_map({mapping}|prev.market)" }} }}')
        values.append(f'eu5ab_legacy_rgo_market_pending_{name} = {{ ' + ' '.join(body) + ' } }')
    body = ['value = 0 if = { limit = { exists = market exists = raw_material "default_price(raw_material)" > 0 }']
    for good in raw_goods():
        body.append(f'if = {{ limit = {{ raw_material = goods:{good} }} '
                    f'value = "market.market_price(goods:{good})" divide = "default_price(goods:{good})" multiply = 100 }}')
    values.append('eu5ab_legacy_rgo_price_percent = { ' + ' '.join(body) + ' } }')
    return {k: v for k, _, v in parse('\n'.join(values))}


class LookupVM(RgoDecisionVM):
    def __init__(self, *args):
        self.raw_tests = 0
        self.absent = set()
        super().__init__(*args)

    def test(self, k, op, v, stack):
        if k == 'raw_material':
            self.raw_tests += 1
        if k == 'exists' and v in self.absent:
            return False
        return super().test(k, op, v, stack)


class RgoLookupTests(unittest.TestCase):
    NAMES = ('market_demand', 'market_supply', 'market_pending_quantity',
             'market_pending_unknown', 'price_percent')

    @classmethod
    def setUpClass(cls):
        fixture = automation.generated_fixture()
        cls.effects = {k: v for k, _, v in parse(fixture.effects)}
        cls.triggers = {k: v for k, _, v in parse(fixture.triggers)}
        cls.values = {k: v for k, _, v in parse(fixture.values)} | legacy_values()

    def setUp(self):
        self.vm = LookupVM(self.effects, self.triggers, self.values)

    def compare(self):
        for name in self.NAMES:
            with self.subTest(value=name):
                self.assertEqual(self.vm.number('eu5ab_rgo_' + name),
                                 self.vm.number('eu5ab_legacy_rgo_' + name))

    def test_all_raw_goods_preserve_each_ledger_and_ignore_other_goods_and_markets(self):
        maps = self.vm.maps['country']
        for index, good in enumerate(raw_goods(), 1):
            for offset, prefix in enumerate(('eu5ab_rgo_pending_output_', 'eu5ab_build_pending_',
                                            'eu5ab_build_future_input_', 'eu5ab_rgo_pending_unknown_',
                                            'eu5ab_build_pending_unknown_', 'eu5ab_build_future_input_unknown_')):
                maps[prefix + good] = {'m1': D(index + offset), 'm2': D(9999)}
        for good in raw_goods():
            self.vm.locations['a']['good'] = good
            self.compare()

    def test_missing_rgo_entries_do_not_skip_ordinary_or_future_input_entries(self):
        vm = self.vm
        vm.maps['country'].clear()
        vm.maps['country']['eu5ab_build_pending_iron'] = {'m1': D(3)}
        vm.maps['country']['eu5ab_build_future_input_iron'] = {'m1': D(5)}
        vm.maps['country']['eu5ab_build_pending_unknown_iron'] = {'m1': D(2)}
        vm.maps['country']['eu5ab_build_future_input_unknown_iron'] = {'m1': D(4)}
        self.compare()
        self.assertEqual(vm.number('eu5ab_rgo_market_pending_quantity'), 3)
        self.assertEqual(vm.number('eu5ab_rgo_market_pending_unknown'), 6)
        self.assertEqual(vm.number('eu5ab_rgo_market_demand'), 105)

    def test_missing_native_readings_unsupported_good_and_genuine_zero_keep_fallbacks(self):
        for absent in ({'market'}, {'raw_material'}, {'owner'}, set()):
            self.vm.absent = absent
            for good in ('iron', 'unsupported_good'):
                self.vm.locations['a']['good'] = good
                self.vm.markets['m1'].update(demand=D(0), supply=D(0))
                self.compare()

    def test_hot_lookups_stop_after_the_matching_raw_good(self):
        # The full traversal tests 52/104/156 raw predicates even when the
        # first good matched. The new traversal tests only that one good.
        self.vm.locations['a']['good'] = raw_goods()[0]
        for name in self.NAMES:
            self.vm.raw_tests = 0
            self.vm.number('eu5ab_rgo_' + name)
            optimized = self.vm.raw_tests
            self.vm.raw_tests = 0
            self.vm.number('eu5ab_legacy_rgo_' + name)
            self.assertEqual(optimized, 1)
            self.assertGreaterEqual(self.vm.raw_tests, len(raw_goods()))


if __name__ == '__main__':
    unittest.main()
