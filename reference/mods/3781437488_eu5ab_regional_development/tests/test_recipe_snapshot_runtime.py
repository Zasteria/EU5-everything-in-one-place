"""Run snapshot effects against the live recipe path, with native facts injected."""
from collections import Counter
import unittest

from src.eu5autobuild.generator import RULES_FILE
from src.eu5autobuild.recipe_snapshot import BUILDING, PROPERTIES, field
from src.eu5autobuild.rules import load_automation_rules
from tests._game_data_fixtures import cached_game_data
from tests.test_production_runtime import ProductionVM


class SnapshotVM(ProductionVM):
    def __init__(self, models, rules):
        super().__init__(models, rules)
        self.selections = Counter()
        self.raw_queries = 0
        self.price_queries = 0

    def value(self, expression):
        if isinstance(expression, str):
            if expression == 'prev':
                return 'building_type:' + self.building
            if expression.startswith('prev.'):
                return self.value(expression[5:])
            if expression.startswith('var:'):
                return self.variables.get(expression[4:], 0)
            if expression.startswith('eu5ab_recipe_') and expression.endswith('_live_selected'):
                self.selections[expression] += 1
            if '.market.market_price(' in expression:
                self.price_queries += 1
        return super().value(expression)

    def predicate(self, key, op, value):
        if key == 'any_location_in_province':
            self.raw_queries += 1
        return super().predicate(key, op, value)

    def execute(self, entries):
        matched = False
        for key, _, value in entries:
            if key in ('if', 'else_if', 'else'):
                if key == 'if':
                    matched = False
                if not matched and (key == 'else' or self.condition(value[0][2])):
                    self.execute(value if key == 'else' else value[1:])
                    matched = True
            elif key == 'switch':
                cases = {k: v for k, _, v in value}
                self.execute(cases.get('building_type:' + self.building, []))
            elif key == 'scope:eu5ab_candidate_location':
                self.execute(value)
            elif key == 'remove_variable':
                self.variables.pop(value, None)
            elif key == 'set_variable':
                if isinstance(value, list):
                    fields = {k: v for k, _, v in value}
                    result = self.value(fields['value'])
                    if result == 0:
                        self.variables.pop(fields['name'], None)
                    else:
                        self.variables[fields['name']] = result
                else:
                    self.variables[value] = True
            elif key in self.effects:
                self.execute(self.effects[key])
            else:
                super().execute([(key, '=', value)])

    def prepare(self):
        self.execute(self.effects['eu5ab_prepare_recipe_score_snapshot'])

    def clear(self):
        self.execute(self.effects['eu5ab_clear_recipe_score_snapshot'])


class RecipeSnapshotRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = cached_game_data()[0]
        cls.rules = load_automation_rules(RULES_FILE)

    def test_all_buildings_match_live_properties_with_shortages_and_unlocks(self):
        vm = SnapshotVM(self.models, self.rules)
        for building, model in self.models.items():
            vm.building = building
            methods = [m for slot in model.slots for m in slot]
            goods = sorted({g for m in methods for g in (*m.inputs, *m.outputs)})
            vm.prices = {g: (i + 1) * .137 for i, g in enumerate(goods)}
            for unlocked, shortage in ((False, False), (True, True), (True, False)):
                vm.advances = {a for m in methods for a in m.unlock_advances} if unlocked else set()
                vm.short_goods = set(goods) if shortage else set(goods[::2])
                vm.raw_goods = set(goods[::2])
                vm.variables['eu5ab_global_native_input_priority'] = 6
                vm.clear()
                expected = {p: vm.value('eu5ab_recipe_expected_' + p) for p in PROPERTIES}
                vm.selections.clear()
                vm.prepare()
                with self.subTest(building=building, unlocked=unlocked, shortage=shortage):
                    self.assertEqual(sum(vm.selections.values()), len(model.slots))
                    self.assertTrue(all(n == 1 for n in vm.selections.values()))
                    for prop in PROPERTIES:
                        self.assertAlmostEqual(vm.value('eu5ab_recipe_expected_' + prop), expected[prop])
                vm.clear()

    def test_disabled_raw_preference_and_zero_inputs_skip_province_queries(self):
        for building in ('mason', 'fishing_village', 'jewelry_guild'):
            vm = SnapshotVM({building: self.models[building]}, self.rules)
            vm.building = building
            for priority in (0, 6):
                vm.variables['eu5ab_global_native_input_priority'] = priority
                vm.raw_queries = 0
                vm.prepare()
                if priority == 0:
                    self.assertNotIn(field('raw_total'), vm.variables)
                    self.assertNotIn(field('raw_matched'), vm.variables)
                    self.assertEqual(vm.raw_queries, 0)
                elif vm.variables.get(field('raw_total'), 0) <= 0:
                    self.assertNotIn(field('raw_matched'), vm.variables)
                    self.assertEqual(vm.raw_queries, 0)

    def test_candidate_and_location_identity_cleanup_and_live_fallback(self):
        vm = SnapshotVM(self.models, self.rules)
        first = vm.variables
        first['eu5ab_global_native_input_priority'] = 6
        vm.building = 'mason'
        vm.prepare()
        saved = dict(first)
        vm.building = 'glass_mill'
        before = vm.price_queries
        live = vm.value('eu5ab_recipe_expected_input_cost')
        self.assertGreater(vm.price_queries, before)  # Wrong candidate cannot hit.
        self.assertEqual(first, saved)
        vm.variables = {'eu5ab_global_native_input_priority': 0}
        vm.prepare()
        self.assertAlmostEqual(vm.value('eu5ab_recipe_expected_input_cost'), live)
        self.assertEqual(first, saved)  # Another location cannot overwrite it.
        vm.clear()
        self.assertFalse(any(k.startswith('eu5ab_recipe_snapshot_') for k in vm.variables))
        vm.variables = first
        vm.building = 'mason'
        before = vm.price_queries
        vm.value('eu5ab_recipe_expected_input_cost')
        self.assertEqual(vm.price_queries, before)
        vm.clear()
        vm.value('eu5ab_recipe_expected_input_cost')
        self.assertGreater(vm.price_queries, before)
        vm.building = 'unknown'
        vm.prepare()
        self.assertNotIn(BUILDING, vm.variables)

    def test_repeated_score_consumers_do_not_repeat_selection_or_prices(self):
        vm = SnapshotVM({'jewelry_guild': self.models['jewelry_guild']}, self.rules)
        vm.building = 'jewelry_guild'
        vm.variables['eu5ab_global_native_input_priority'] = 6
        vm.prepare()
        calls, prices = vm.selections.copy(), vm.price_queries
        for _ in range(3):
            vm.value('eu5ab_recipe_economic_efficiency_score')
            vm.value('eu5ab_native_input_coverage_percent')
        self.assertEqual(vm.selections, calls)
        self.assertEqual(vm.price_queries, prices)

    def test_zero_valued_snapshot_hits_even_when_engine_drops_numeric_zero(self):
        vm = SnapshotVM({'mason': self.models['mason']}, self.rules)
        vm.building = 'mason'
        vm.prices = {'masonry': 0, 'stone': 0, 'clay': 0}
        vm.prepare()
        self.assertNotIn(field('input_cost'), vm.variables)
        self.assertIn(field('input_cost') + '_ready', vm.variables)
        calls = vm.price_queries
        self.assertEqual(vm.value('eu5ab_recipe_expected_input_cost'), 0)
        self.assertEqual(vm.value('eu5ab_recipe_expected_output_value'), 0)
        self.assertEqual(vm.price_queries, calls)
