"""Compare typed scoring with the retained live path across the real catalog."""
from collections import Counter
import re
import unittest

from src.eu5autobuild.generator import _catalog_building_ids
from src.eu5autobuild.recipe_snapshot import field
from tests import _generated as automation
from tests._game_data_fixtures import cached_game_data
from tests._governor_script_vm import parse
from tests.test_recipe_snapshot_runtime import SnapshotVM


class NeedScoreVM(SnapshotVM):
    def __init__(self, fixture, rules, models):
        super().__init__(models, rules)
        self.definitions.update({k: v for k, _, v in parse(fixture.values)})
        self.effects.update({k: v for k, _, v in parse(fixture.effects)})
        self.triggers.update({k: v for k, _, v in parse(fixture.triggers)})
        self.generic = next(v for k, _, v in self.definitions['eu5ab_universal_need_score'] if k == 'else')
        self.market_exists = True
        self.food_percent = 1
        self.food_balance = 1
        self.exhaustion = False
        self.war = False
        self.upgrade = False
        self.supply = {}
        self.demand = {}
        self.raw_output = 0
        self.market_reads = Counter()
        self.type_tests = 0

    def value(self, expression):
        if isinstance(expression, str):
            match = re.fullmatch(r'(goods_supply_in_market|goods_demand_in_market|market_price|default_price)\(goods:([a-z_]+)\)', expression)
            if match:
                kind, good = match.groups()
                self.market_reads[kind, good] += 1
                return {'goods_supply_in_market': self.supply,
                        'goods_demand_in_market': self.demand,
                        'market_price': self.prices,
                        'default_price': {}}[kind].get(good, 1)
            if expression == 'market_food_percentage':
                return self.food_percent
            if expression == 'market_monthly_food_balance':
                return self.food_balance
            if expression == 'raw_material_output':
                return self.raw_output
        return super().value(expression)

    def predicate(self, key, op, value):
        if key == 'this':
            self.type_tests += 1
        if key == 'scope:eu5ab_candidate_location.market':
            return self.market_exists and self.condition(value)
        if key == 'is_projected_to_run_out_of_food_stockpile':
            return self.exhaustion == (value == 'yes')
        if key == 'at_war':
            return self.war == (value == 'yes')
        if key == 'eu5ab_candidate_replaces_existing_building':
            return self.upgrade == (value == 'yes')
        if op == '<' and isinstance(value, list):
            return self.value(key) < self.value(value)
        return super().predicate(key, op, value)


class NeedScoreSnapshotRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = automation.generated_fixture()
        cls.models = cached_game_data()[0]
        # Load the same input, without invoking another test class's setup.
        from src.eu5autobuild.generator import RULES_FILE
        from src.eu5autobuild.rules import load_automation_rules
        cls.rules = load_automation_rules(RULES_FILE)

    def vm(self):
        return NeedScoreVM(self.fixture, self.rules, self.models)

    def test_all_catalog_buildings_match_live_scores_and_select_each_slot_once(self):
        vm = self.vm()
        all_goods = set(self.rules.essential_goods) | set(self.rules.input_goods) | set(self.rules.food_goods)
        all_goods |= {g for model in self.models.values() for slot in model.slots for method in slot for g in (*method.inputs, *method.outputs)}
        all_advances = {a for model in self.models.values() for slot in model.slots for method in slot for a in method.unlock_advances}
        for case in range(6):
            vm.market_exists = case != 0
            vm.food_percent = (1, 0, .25, .5, 1, 1)[case]
            vm.food_balance = -1 if case in (1, 2, 3) else 1
            vm.exhaustion = case in (1, 5)
            vm.war = case in (2, 4)
            vm.upgrade = case in (3, 5)
            vm.level = case * 1.25
            vm.raw_output = 10 if case % 2 else 0
            vm.raw_goods = {'wheat', 'rice', 'millet'} if case == 5 else {('wheat', 'rice', 'millet')[case % 3]}
            vm.advances = all_advances if case % 2 else set()
            vm.variables.update(eu5ab_global_native_input_priority=6 if case % 2 else 0,
                                eu5ab_global_emergency_food_exhaustion_override=0 if case == 5 else 1,
                                eu5ab_global_emergency_food_stockpile_override=0 if case == 5 else 1,
                                eu5ab_global_stop_input_shortage=case % 2)
            vm.supply = {g: (0, 0, .65, .9, 2, 1)[case] for g in all_goods}
            vm.demand = {g: 1 for g in all_goods}
            vm.prices = {g: (1, 2, 1, 1.5, 3, 1)[case] for g in all_goods}
            for building in _catalog_building_ids(self.fixture.catalog):
                vm.clear()
                vm.building = building
                expected = vm.run(vm.generic)
                vm.selections.clear()
                vm.prepare()
                with self.subTest(building=building, case=case):
                    self.assertAlmostEqual(vm.value('eu5ab_universal_need_score'), expected)
                    self.assertEqual(sum(vm.selections.values()), sum(bool(slot) for slot in self.models[building].slots))
                    before = vm.market_reads.copy(), vm.selections.copy(), vm.price_queries
                    vm.value('eu5ab_universal_need_score')
                    self.assertEqual((vm.market_reads, vm.selections, vm.price_queries), before)

    def test_zero_cache_wrong_building_other_location_and_clear_restore_live_path(self):
        vm = self.vm()
        vm.building = 'granary'
        vm.prepare()
        self.assertNotIn(field('need_score'), vm.variables)  # Engine drops numeric zero.
        self.assertIn(field('need_score') + '_ready', vm.variables)
        before = vm.type_tests
        self.assertEqual(vm.value('eu5ab_universal_need_score'), 0)
        self.assertEqual(vm.type_tests, before)
        saved = dict(vm.variables)
        vm.building = 'fishing_village'
        vm.food_percent = 0
        expected = vm.run(vm.generic)
        self.assertEqual(vm.value('eu5ab_universal_need_score'), expected)
        self.assertEqual(vm.variables, saved)
        vm.variables = {}
        vm.prepare()
        vm.food_percent = 1
        self.assertEqual(vm.value('eu5ab_universal_need_score'), expected)
        vm.clear()
        self.assertEqual(vm.value('eu5ab_universal_need_score'), vm.run(vm.generic))
        self.assertNotEqual(vm.value('eu5ab_universal_need_score'), expected)
        vm.variables = saved
        vm.building = 'granary'
        self.assertEqual(vm.value('eu5ab_universal_need_score'), 0)
        vm.building = 'unknown'
        vm.prepare()
        self.assertEqual(vm.value('eu5ab_universal_need_score'), vm.run(vm.generic))

    def test_typed_score_avoids_catalog_walk_and_unrelated_market_queries(self):
        vm = self.vm()
        for building in ('mason', 'tools_workshop', 'windmill', 'granary'):
            vm.building = building
            vm.clear()
            vm.type_tests = 0
            expected = vm.run(vm.generic)
            generic_type_tests = vm.type_tests
            vm.type_tests = 0
            vm.market_reads.clear()
            vm.prepare()
            self.assertEqual(vm.value('eu5ab_universal_need_score'), expected)
            self.assertLess(vm.type_tests, generic_type_tests)
            allowed = set(self.fixture.catalog.get(building).output_goods)
            allowed |= {g for slot in self.models[building].slots for method in slot for g in (*method.inputs, *method.outputs)}
            if building == 'windmill':
                allowed |= {'wheat', 'rice', 'millet'}
            self.assertFalse({good for _, good in vm.market_reads} - allowed)
