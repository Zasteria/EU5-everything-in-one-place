"""Price boundaries execute generated arithmetic with EU5 fixed-point rounding."""
from collections import Counter
from decimal import Decimal, ROUND_DOWN
import math
import re
import unittest

from src.eu5autobuild import market_price_cache, output_prices
from src.eu5autobuild.output_prices import OutputPrice, assess
from tests._generated import generated_fixture
from tests._game_data_fixtures import cached_game_data
from tests._governor_script_vm import parse
from tests.test_engine import RULES
from tests.test_need_score_snapshot_runtime import NeedScoreVM


class PriceVM(NeedScoreVM):
    def __init__(self):
        super().__init__(generated_fixture(), RULES, cached_game_data()[0])
        self.building = 'mason'
        self.variables.update(eu5ab_global_price_min=80, eu5ab_global_price_max=125,
                              eu5ab_global_emergency_food_stockpile_override=1,
                              eu5ab_global_emergency_food_exhaustion_override=1)

    def value(self, expression):
        result = super().value(expression)
        return self.normalize_arithmetic(result)

    def normalize_arithmetic(self, result):
        if isinstance(result, (int, float, Decimal)) and not isinstance(result, bool):
            return Decimal(str(result)).quantize(Decimal('0.00001'), rounding=ROUND_DOWN)
        return result

    def predicate(self, key, op, value):
        if key == 'exists' and value == 'market':
            return self.market_exists
        return super().predicate(key, op, value)

    def allowed(self):
        return self.condition(self.triggers['eu5ab_output_not_oversupplied'])


class OutputPriceRuntimeTests(unittest.TestCase):
    def test_price_references_have_unique_definitions_without_expanding_cache(self):
        fixture = generated_fixture()
        models = cached_game_data()[0]
        required = output_prices.price_goods(models, RULES)
        baseline = market_price_cache.render(models, fixture.catalog, RULES, required_goods=set())
        complete = market_price_cache.render(models, fixture.catalog, RULES, required_goods=required)
        self.assertEqual(complete[:2], baseline[:2])
        definitions = Counter(name for name, _, _ in parse(fixture.values))
        references = set(re.findall(r'\beu5ab_market_price_[a-z_]+\b', fixture.triggers + fixture.values))
        self.assertTrue(references)
        for name in references:
            with self.subTest(name=name):
                self.assertEqual(definitions[name], 1)

    def test_uncached_price_helpers_read_live_prices(self):
        vm = PriceVM()
        required = output_prices.price_goods(cached_game_data()[0], RULES)
        uncached = {good for good in required if f'eu5ab_prepare_market_price_{good}' not in vm.effects}
        self.assertIn('tea', uncached)
        for good in sorted(uncached):
            name = market_price_cache.price_value(good)
            with self.subTest(good=good):
                self.assertEqual(vm.definitions[name], [
                    ('value', '=', f'scope:eu5ab_candidate_location.market.market_price(goods:{good})')
                ])
                before = vm.price_queries
                for price in (0, .9, 1.4):
                    vm.prices[good] = price
                    self.assertEqual(float(vm.value(name)), price)
                self.assertEqual(vm.price_queries - before, 3)

    def test_floor_linear_interval_and_high_reward(self):
        vm = PriceVM()
        for price, factor, bonus in ((.79, 0, 0), (.8, 0, 0), (.9, .5, 0),
                                     (1, 1, 0), (1.125, 1, 70), (1.25, 1, 140), (2, 1, 140)):
            vm.prices['masonry'] = price
            with self.subTest(price=price):
                self.assertEqual(vm.allowed(), factor > 0)
                self.assertAlmostEqual(float(vm.value('eu5ab_output_price_factor')), factor, places=4)
                self.assertAlmostEqual(float(vm.value('eu5ab_output_high_price_bonus')), bonus, places=3)

    def test_no_fixed_high_price_shortage_jump(self):
        vm = PriceVM()
        vm.prices['masonry'] = 1.25
        before = vm.value('eu5ab_universal_need_score') + vm.value('eu5ab_output_high_price_bonus')
        vm.prices['masonry'] = 1.25001
        after = vm.value('eu5ab_universal_need_score') + vm.value('eu5ab_output_high_price_bonus')
        self.assertEqual(before, after)
        vm.demand['masonry'], vm.supply['masonry'] = 1, .5
        self.assertGreater(vm.value('eu5ab_universal_need_score'), before)

    def test_signed_planning_and_profit_ranks_are_discounted_once(self):
        vm = PriceVM()
        vm.prices['masonry'] = .9
        for score, expected in ((100, 50), (-100, -200), (0, 0)):
            vm.native_values['eu5ab_unadjusted_candidate_score'] = score
            self.assertAlmostEqual(float(vm.value('eu5ab_price_adjusted_candidate_score')), expected, places=3)

    def test_missing_market_is_not_an_outputless_building(self):
        vm = PriceVM()
        vm.market_exists = False
        self.assertFalse(vm.allowed())
        vm.building = 'granary'
        self.assertTrue(vm.allowed())
        self.assertEqual(vm.value('eu5ab_output_high_price_bonus'), 0)

    def test_small_positive_coefficient_survives_weight_rounding(self):
        vm = PriceVM()
        vm.variables['eu5ab_global_price_min'] = 1
        vm.prices['masonry'] = .01001
        self.assertTrue(vm.allowed())
        self.assertGreater(vm.value('eu5ab_output_price_factor'), 0)
        vm.native_values['eu5ab_unadjusted_candidate_score'] = -1000000000000
        self.assertGreaterEqual(vm.value('eu5ab_price_adjusted_candidate_score'), -90000000000000)

    def test_inverted_settings_and_emergency_switches(self):
        vm = PriceVM()
        vm.variables.update(eu5ab_global_price_min=120, eu5ab_global_price_max=100)
        vm.prices['masonry'] = 1.2
        self.assertFalse(vm.allowed())
        self.assertEqual(vm.value('eu5ab_output_high_price_bonus'), 0)
        vm.prices['masonry'] = 1.21
        self.assertTrue(vm.allowed())
        self.assertEqual(vm.value('eu5ab_output_high_price_bonus'), 140)
        vm.building = 'fishing_village'
        vm.prices['fish'] = .5
        vm.exhaustion = True
        self.assertTrue(vm.allowed())
        self.assertEqual(vm.value('eu5ab_output_price_factor'), 1)
        vm.variables['eu5ab_global_emergency_food_exhaustion_override'] = 0
        self.assertFalse(vm.allowed())

    def test_economic_estimate_changes_output_identity_for_all_consumers(self):
        vm = PriceVM()
        vm.building = 'market_village'
        vm.prices.update(tools=.5, beer=4, jewelry=.1, weaponry=.1, pottery=.1)
        self.assertEqual(vm.value('eu5ab_recipe_market_village_0_selected'), 2)
        self.assertTrue(vm.allowed())
        self.assertEqual(vm.value('eu5ab_output_high_price_bonus'), 140)
        vm.prices['beer'] = .4
        self.assertFalse(vm.allowed())

    def test_multi_output_weights_and_invalid_readings(self):
        outputs = (OutputPrice(9, 1, .7), OutputPrice(1, 1, 2))
        factor, bonus = assess(outputs, 80, 125)
        self.assertAlmostEqual(factor, .1)
        self.assertAlmostEqual(bonus, .1)
        self.assertEqual(assess((), 80, 125), (1, 0))
        for price in (None, math.nan, math.inf, -1):
            self.assertEqual(assess((OutputPrice(1, 1, price),), 80, 125), (0, 0))
        self.assertEqual(assess((OutputPrice(1, 1, 1.4),), 150, 125), (0, 0))


if __name__ == '__main__':
    unittest.main()
