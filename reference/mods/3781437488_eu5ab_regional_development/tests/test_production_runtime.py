"""Execute generated recipe selection, prices, native fit and recovery routing.

Only engine facts (market data, geography and unlocks) are injected. These tests
exercise the generated branches; they do not claim to emulate native PM choice.
"""
import json
from pathlib import Path
import re
import tempfile
import unittest

from src.eu5autobuild.generator import (
    RULES_FILE, render_native_input_script_values, render_recipe_script_values,
    _upstream_output_shortage_condition_lines,
)
from src.eu5autobuild.policy import BuildingCatalog
from src.eu5autobuild.production import (
    extract_production_models, production_models_as_json, production_models_from_json,
    render_production,
)
from src.eu5autobuild.rules import load_automation_rules
from tests._game_data_fixtures import cached_game_data
from tests._governor_script_vm import parse
from tests.test_candidate_score_optimizations import ScoreVM


class ProductionVM(ScoreVM):
    def __init__(self, models, rules):
        triggers, _, effects = render_production(models, rules)
        values = render_recipe_script_values(models, rules) + render_native_input_script_values(models, [], rules)
        super().__init__({k: v for k, _, v in parse(values)}, {k: v for k, _, v in parse(triggers)})
        self.effects = {k: v for k, _, v in parse(effects)}
        self.advances, self.raw_goods, self.produced = set(), set(), set()
        self.prices = {}
        self.variables['eu5ab_global_stop_input_shortage'] = 1
        self.native_values['building_base_cost_in_gold'] = 100
        self.development = 0

    def value(self, value):
        if isinstance(value, str) and '.market.market_price(' in value:
            return self.prices.get(re.search(r'goods:([a-z_]+)', value)[1], 1)
        if isinstance(value, str) and value.startswith('eu5ab_market_effective_demand_'):
            return 100  # No outstanding demand sources in recipe-only scenarios.
        if isinstance(value, str) and 'goods_supply_in_market(' in value:
            good = re.search(r'goods:([a-z_]+)', value)[1]
            return 0 if good in self.short_goods else 100
        if value == 'development':
            return self.development
        return super().value(value)

    def predicate(self, key, op, value):
        if key in ('AND', 'custom_tooltip', 'scope:eu5ab_candidate_location.owner',
                   'any_market_present_in_country', 'market'):
            return self.condition(value)
        if key == 'text':
            return True
        if key == 'has_advance':
            return value in self.advances
        if key == 'is_produced_in_market':
            return value.removeprefix('goods:') in self.produced
        if key in ('scope:eu5ab_candidate_location.province', 'any_location_in_province'):
            return self.condition(value)
        if key == 'raw_material':
            return value.removeprefix('goods:') in self.raw_goods
        if key.startswith('eu5ab_recipe_') and key in self.triggers:
            return self.condition(self.triggers[key]) == (value == 'yes')
        if op == '<' and not isinstance(value, list):
            return self.value(key) < self.value(value)
        return super().predicate(key, op, value)

    def available(self):
        return self.condition(self.triggers['eu5ab_inputs_available'])


class ProductionRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = cached_game_data()[0]
        cls.rules = load_automation_rules(RULES_FILE)

    def vm(self, building):
        vm = ProductionVM({building: self.models[building]}, self.rules)
        vm.building = building
        return vm

    def test_mason_clay_is_not_vetoed_by_unused_stone_and_all_scores_use_clay(self):
        vm = self.vm('mason')
        vm.short_goods = {'stone'}
        vm.raw_goods = {'clay'}
        vm.prices = dict(stone=99, clay=2, masonry=5)
        self.assertTrue(vm.available())
        self.assertEqual(vm.value('eu5ab_recipe_mason_0_selected'), 2)
        self.assertAlmostEqual(vm.value('eu5ab_recipe_expected_input_cost'), .833 * 2)
        self.assertAlmostEqual(vm.value('eu5ab_recipe_expected_output_value'), .5 * 5)
        self.assertEqual(vm.value('eu5ab_native_input_coverage_percent'), 100)
        self.assertEqual(vm.value('eu5ab_native_input_shortage_factor'), 1)

    def test_mason_both_short_uses_one_complete_fallback_recipe(self):
        vm = self.vm('mason')
        vm.short_goods = {'stone', 'clay'}
        self.assertFalse(vm.available())
        self.assertEqual(vm.value('eu5ab_recipe_mason_0_selected'), 1)
        vm.variables['eu5ab_global_stop_input_shortage'] = 0
        self.assertTrue(vm.available())
        self.assertEqual(vm.value('eu5ab_native_input_shortage_factor'), self.rules.native_input_fit.shortage_discount)

    def test_cloth_guild_every_alternative_is_independent(self):
        slot = self.models['cloth_guild'].slots[0]
        for index, method in enumerate(slot, 1):
            with self.subTest(method=method.production_method_id):
                vm = self.vm('cloth_guild')
                inputs = set(method.inputs)
                vm.short_goods = set().union(*(set(m.inputs) for m in slot)) - inputs
                self.assertTrue(vm.available())
                self.assertEqual(vm.value('eu5ab_recipe_cloth_guild_0_selected'), index)
                self.assertAlmostEqual(vm.value('eu5ab_recipe_expected_input_cost'), sum(method.inputs.values()))

    def test_technology_locked_paper_recipe_cannot_rescue_short_leather(self):
        vm = self.vm('paper_guild')
        vm.short_goods = {'leather'}
        self.assertFalse(vm.available())
        method = self.models['paper_guild'].slots[0][1]
        self.assertTrue(method.unlock_advances)
        vm.advances.update(method.unlock_advances)
        self.assertTrue(vm.available())
        self.assertEqual(vm.value('eu5ab_recipe_paper_guild_0_selected'), 2)
        vm.short_goods.add('lumber')
        self.assertFalse(vm.available())

    def test_multiple_slots_require_a_feasible_recipe_in_each_slot(self):
        vm = self.vm('fine_cloth_guild')
        vm.short_goods = {'cloth', 'silk', 'alum'}
        self.assertTrue(vm.available())  # wool in slot 0; dyes in slot 1
        self.assertEqual(vm.value('eu5ab_recipe_fine_cloth_guild_0_selected'), 2)
        self.assertEqual(vm.value('eu5ab_recipe_fine_cloth_guild_1_selected'), 1)
        self.assertAlmostEqual(vm.value('eu5ab_recipe_expected_output_value'), .6)
        self.assertAlmostEqual(vm.value('eu5ab_recipe_expected_input_cost'), 1 + .125)
        # A second mandatory slot remains required, even when slot 0 is viable.
        # Synthetic slot below uses only protected inputs so this is independent
        # of the existing industrial-input goods domain (which excludes fur).

    def test_no_raw_input_has_zero_coverage_without_dividing_by_zero(self):
        vm = self.vm('wharf')
        self.assertEqual(vm.value('eu5ab_native_input_coverage_percent'), 0)

    def test_single_recipe_cost_avoids_supply_queries_and_fit_is_quantity_weighted(self):
        vm = self.vm('iron_foundry')
        method = self.models['iron_foundry'].slots[0][0]
        vm.raw_goods = {'coal'}
        self.assertAlmostEqual(vm.value('eu5ab_recipe_expected_input_cost'), sum(method.inputs.values()))
        expected = method.raw_inputs['coal'] / sum(method.raw_inputs.values()) * 100
        self.assertAlmostEqual(vm.value('eu5ab_native_input_coverage_percent'), expected, places=4)
        self.assertEqual(vm.market_queries, [])

    def test_upstream_shortage_does_not_require_a_blocked_downstream(self):
        from src.eu5autobuild.generator import CATALOG_FILE
        from src.eu5autobuild.policy import load_building_catalog
        catalog = load_building_catalog(CATALOG_FILE)
        body = parse('test = {\n' + '\n'.join(_upstream_output_shortage_condition_lines(catalog, self.rules, '', True)) + '\n}')[0][2]
        building = next(b for b in catalog.source_buildings_by_good['cloth'] if b in self.models)
        vm = self.vm(building)
        # This test isolates output identity/routing. The market reservation
        # predicate is exercised with real maps in test_market_supply_runtime.
        vm.triggers['eu5ab_market_needs_cloth'] = [('always', '=', 'yes')]
        vm.short_goods = {'cloth'}
        self.assertTrue(vm.condition(body))
        vm.variables['eu5ab_global_fill_market_shortages_when_idle'] = 1
        self.assertTrue(vm.condition(body))

    def test_schema_roundtrip_is_stable_and_marks_approximation(self):
        encoded = production_models_as_json(self.models)
        payload = json.loads(encoded)
        self.assertTrue(payload['active_method_readable'])
        self.assertFalse(payload['new_build_method_readable'])
        self.assertEqual(encoded, production_models_as_json(production_models_from_json(payload)))


class ProductionExtractionTests(unittest.TestCase):
    def test_slots_conditions_unlocks_global_inline_references_and_zero_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            common = root / 'game/in_game/common'
            for name in ('building_types', 'production_methods', 'goods', 'advances'):
                (common / name).mkdir(parents=True)
            (common / 'goods/goods.txt').write_text('stone = {} clay = {} tools = { category = produced }', encoding='utf-8')
            (common / 'building_types/buildings.txt').write_text('''
                shop = {
                    unique_production_methods = {
                        stone_method = { stone = 1 produced = tools output = 2
                            potential = { has_variable = enabled }
                            allow = { scope:target ?= { development >= 20 } }
                        }
                        clay_method = { clay = 2 produced = tools output = 3 }
                    }
                    possible_production_methods = { maintenance }
                }
                other = { possible_production_methods = { clay_method } }
            ''', encoding='utf-8')
            (common / 'production_methods/methods.txt').write_text('maintenance = { tools = 1 }', encoding='utf-8')
            (common / 'advances/unlocks.txt').write_text('tech = { unlock_production_method = clay_method }', encoding='utf-8')
            catalog = BuildingCatalog.from_mapping({'buildings': [{'id': 'shop'}, {'id': 'other'}]})
            models = extract_production_models(root, catalog)
            self.assertEqual([len(slot) for slot in models['shop'].slots], [2, 1])
            self.assertEqual(models['shop'].slots[0][1].unlock_advances, ('tech',))
            self.assertEqual(models['shop'].slots[1][0].outputs, {})
            self.assertIn('>= 20', models['shop'].slots[0][0].allow)
            self.assertEqual(models['other'].slots[0][0].inputs, {'clay': 2})
            vm = ProductionVM(models, load_automation_rules(RULES_FILE))
            vm.building = 'shop'
            vm.variables['eu5ab_global_stop_input_shortage'] = 0
            self.assertFalse(vm.available())  # no available recipe even with guard off
            vm.variables['enabled'] = 1
            vm.development = 19
            self.assertFalse(vm.available())
            vm.development = 20
            self.assertTrue(vm.available())
            vm.variables['eu5ab_global_stop_input_shortage'] = 1
            vm.short_goods = {'tools'}
            self.assertFalse(vm.available())  # independent maintenance slot
            vm.short_goods = {'stone'}
            self.assertFalse(vm.available())  # alternative still technology locked
            vm.advances.add('tech')
            self.assertTrue(vm.available())
            self.assertEqual(vm.value('eu5ab_recipe_expected_input_cost'), 3)
