"""Run generated irrigation predicates against native facts and save regressions."""
from dataclasses import replace
from itertools import product
import unittest

from src.eu5autobuild.engine import (
    AutomationContext, BuildingCandidate, GoodsMarketState, LocationState,
    MarketState, PauseReason, first_blocking_reason, irrigation_demand_present,
    score_candidate_components,
)
from src.eu5autobuild.generator import (
    CATALOG_FILE, RULES_FILE, _food_support_trigger_lines,
    _support_trigger_lines, render_irrigation_triggers,
)
from src.eu5autobuild.policy import load_building_catalog
from src.eu5autobuild.rules import AutomationThresholds, load_automation_rules
from tests._governor_script_vm import parse
from tests.test_candidate_score_optimizations import ScoreVM
from tests.test_engine import policy


class IrrigationVM(ScoreVM):
    def __init__(self, rules, context):
        triggers = {k: v for k, _, v in parse(render_irrigation_triggers(rules))}
        super().__init__({}, triggers)
        self.building = 'irrigation_systems'
        self.context = context
        capacity = context.location.population_capacity
        self.native_values = {
            'location_max_population': capacity or 0,
            'location_population_percentage': context.location.population / capacity if capacity else 0,
            'market_food_percentage': context.market.food_stockpile_ratio,
            'market_monthly_food_balance': context.market.monthly_food_balance,
        }

    def predicate(self, key, op, value):
        if key == 'AND':
            return self.condition(value)
        if key == 'exists':
            if value != 'market':
                raise AssertionError(value)
            return self.context.market.available
        if key == 'market':
            return self.context.market.available and self.condition(value)
        if key == 'is_projected_to_run_out_of_food_stockpile':
            return self.context.market.projected_food_exhaustion == (value == 'yes')
        if key in self.triggers:
            return self.condition(self.triggers[key]) == (value == 'yes')
        if op == '<':
            return self.value(key) < self.value(value)
        return super().predicate(key, op, value)

    def allowed(self):
        return self.condition(self.triggers['eu5ab_candidate_has_irrigation_demand'])


class IrrigationDemandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = load_automation_rules(RULES_FILE)
        cls.catalog = load_building_catalog(CATALOG_FILE)
        cls.policy = policy(allowed_buildings=['irrigation_systems'])
        cls.building = BuildingCandidate('irrigation_systems', (), 40, 1)

    def context(self, stock=1, balance=0, exhausted=False, population=27.545, capacity=100, market=True):
        return AutomationContext(
            market=MarketState(food_stockpile_ratio=stock, monthly_food_balance=balance,
                               projected_food_exhaustion=exhausted, available=market),
            location=LocationState(
                population=population, population_capacity=capacity,
                fully_staffed_building_levels=0, supported_building_levels=100,
            ),
        )

    def test_boundaries_and_independent_food_or_capacity_routes(self):
        cases = [
            ({}, False),
            ({'stock': .25}, True),
            ({'stock': .25001}, False),
            ({'stock': .5, 'balance': -1}, True),
            ({'stock': .50001, 'balance': -1}, False),
            ({'stock': .5, 'balance': 0}, False),
            ({'stock': .5, 'balance': 1}, False),
            ({'exhausted': True}, True),
            ({'population': 90}, True),
            ({'population': 89.999}, False),
            ({'population': 120}, True),
            ({'capacity': 0}, False),
            ({'capacity': None}, False),
            ({'market': False, 'stock': 0, 'exhausted': True}, False),
            ({'market': False, 'population': 90}, True),
        ]
        for facts, expected in cases:
            with self.subTest(facts=facts):
                context = self.context(**facts)
                self.assertEqual(IrrigationVM(self.rules, context).allowed(), expected)
                self.assertEqual(irrigation_demand_present(context, self.rules), expected)

    def test_generated_and_offline_gate_agree_across_market_and_capacity_states(self):
        for stock, balance, exhausted, population, capacity, market in product(
            (.2, .4, .8), (-1, 1), (False, True), (25, 90), (0, 100), (False, True),
        ):
            context = self.context(stock, balance, exhausted, population, capacity, market)
            self.assertEqual(IrrigationVM(self.rules, context).allowed(),
                             irrigation_demand_present(context, self.rules))

    def test_capacity_ratio_is_configurable_and_invalid_values_are_rejected(self):
        thresholds = replace(self.rules.thresholds, irrigation_population_capacity_ratio=.95)
        rules = replace(self.rules, thresholds=thresholds)
        self.assertFalse(IrrigationVM(rules, self.context(population=94)).allowed())
        self.assertTrue(IrrigationVM(rules, self.context(population=95)).allowed())
        from dataclasses import asdict
        for invalid in (0, -1, 1.01, float('nan')):
            raw = asdict(thresholds) | {'irrigation_population_capacity_ratio': invalid}
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                AutomationThresholds.from_mapping(raw)

    def test_yexian_food_snapshot_does_not_justify_building_without_capacity_pressure(self):
        # 1424.3.5 save: food=188265.19754, max=188485, market has a surplus.
        # Capacity is deliberately a scenario, NOT a value recovered from this save.
        context = self.context(stock=188265.19754 / 188485, balance=9298.81716, capacity=100)
        candidate = replace(self.building, existing_levels=6, price_ratio=1.61112,
                            potential_profit=1000)
        self.assertFalse(IrrigationVM(self.rules, context).allowed())
        self.assertEqual(first_blocking_reason(self.policy, candidate, 550000, 550000,
                                              context=context, rules=self.rules),
                         PauseReason.NO_IRRIGATION_NEED)
        crowded = replace(context, location=replace(context.location, population_capacity=30))
        self.assertTrue(IrrigationVM(self.rules, crowded).allowed())

    def test_irrigation_supports_food_but_no_traded_good_or_upstream_source(self):
        self.assertEqual(self.catalog.get('irrigation_systems').output_goods, ())
        for good in ('wheat', 'rice', 'maize', 'millet'):
            self.assertNotIn('irrigation_systems', self.catalog.source_buildings_by_good.get(good, ()))
            self.assertNotIn('building_type:irrigation_systems',
                             '\n'.join(_support_trigger_lines((good,), self.catalog, '')))
        self.assertIn('building_type:irrigation_systems',
                      '\n'.join(_food_support_trigger_lines(self.catalog, self.rules, '')))

    def test_grain_prices_neither_boost_nor_veto_needed_irrigation(self):
        context = self.context(population=90)
        scores = []
        for price in (.1, 1, 1.61112, 10):
            market = replace(context.market, goods={'millet': GoodsMarketState(1, 100, price)})
            context = replace(context, market=market)
            candidate = replace(self.building, price_ratio=price)
            scores.append(score_candidate_components(self.policy, candidate, context, self.rules))
            self.assertEqual(first_blocking_reason(self.policy, candidate, 1000, 2000,
                                                  context=context, rules=self.rules), PauseReason.NONE)
        self.assertTrue(all(score == scores[0] for score in scores))

    def test_food_emergency_scoring_survives_removing_fake_goods(self):
        scores = score_candidate_components(self.policy, self.building,
                                            self.context(stock=.2, exhausted=True), self.rules)
        self.assertEqual(scores['market_need'], self.rules.scores.food_projected_exhaustion)

    def test_non_irrigation_is_not_gated_and_other_safety_checks_still_apply(self):
        vm = IrrigationVM(self.rules, self.context(capacity=0, market=False))
        vm.building = 'farming_village'
        self.assertTrue(vm.allowed())
        for changes, reason in [({'inputs_available': False}, PauseReason.INPUT_SHORTAGE),
                                ({'labor_available': False}, PauseReason.LABOR_SHORTAGE),
                                ({'cost': 1001}, PauseReason.BUDGET_EXHAUSTED)]:
            self.assertEqual(first_blocking_reason(self.policy, replace(self.building, **changes),
                                                  1000, 2000, context=self.context(stock=.2),
                                                  rules=self.rules), reason)


if __name__ == '__main__':
    unittest.main()
