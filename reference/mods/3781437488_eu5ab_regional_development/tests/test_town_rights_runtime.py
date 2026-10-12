"""Run the generated preference arithmetic with injected native location facts."""
from pathlib import Path
import re
import unittest

from src.eu5autobuild.generator import (
    CATALOG_FILE, POLICY_FILE, RULES_FILE, TEMPLATE_SLOTS,
    render_needs_script_values,
)
from src.eu5autobuild.policy import load_building_catalog, load_policies
from src.eu5autobuild.production import BuildingProduction, ProductionMethod, script_blocks
from src.eu5autobuild.rules import load_automation_rules
from src.eu5autobuild.town_rights import (
    BUILDING_RIGHTS, FOOD_RIGHTS, OUTPUT_RIGHTS, RGO_RIGHTS, STORAGE_RIGHTS,
    SCORE_CACHE, SCORE_CACHE_BUILDING, SCORE_CACHE_READY,
    render_town_rights_effects, render_town_rights_values,
)
from tests._game_data_fixtures import cached_game_data
from tests._governor_script_vm import parse
from tests.test_production_runtime import ProductionVM


class RightsVM(ProductionVM):
    def __init__(self, models, rules):
        super().__init__(models, rules)
        self.definitions.update({k: v for k, _, v in parse(render_town_rights_values(models, rules))})
        self.base_prices = {}
        self.demands = set()
        self.full_rgo = False

    def value(self, value):
        if value == 'prev':
            return f'building_type:{self.building}'
        if isinstance(value, str) and value.startswith('prev.'):
            return self.value(value[5:])
        if isinstance(value, str) and value.startswith('default_price(goods:'):
            return self.base_prices.get(re.search(r'goods:([a-z_]+)', value)[1], 1)
        return super().value(value)

    def predicate(self, key, op, value):
        if key in ('eu5ab_windmill_output_demand', 'eu5ab_irrigation_food_demand',
                   'eu5ab_granary_storage_demand'):
            return key in self.demands
        if key == 'is_full_expanded_rgo':
            return self.full_rgo == (value == 'yes')
        return super().predicate(key, op, value)

    def score(self):
        return self.value('eu5ab_town_rights_candidate_score')

    def prepare_town_rights_score(self):
        def execute(entries):
            matched = False
            for key, _, value in entries:
                fields = {k: v for k, _, v in value} if isinstance(value, list) else {}
                if key in ('if', 'else_if', 'else'):
                    if key == 'if':
                        matched = False
                    if not matched and (key == 'else' or self.condition(fields['limit'])):
                        execute([entry for entry in value if entry[0] != 'limit'])
                        matched = True
                elif key == 'switch':
                    execute(fields.get(f'building_type:{self.building}', fields.get('fallback', [])))
                elif key == 'scope:eu5ab_candidate_location':
                    execute(value)
                elif key == 'remove_variable':
                    self.variables.pop(value, None)
                elif key == 'set_variable':
                    name = fields['name'] if fields else value
                    result = self.value(fields['value']) if fields else True
                    if result == 0:
                        self.variables.pop(name, None)
                    else:
                        self.variables[name] = result
                else:
                    raise AssertionError(key)
        execute(self.effects['eu5ab_prepare_town_rights_candidate_score'])


def method(outputs, inputs=None, **kwargs):
    return ProductionMethod('example', 'method', outputs, inputs or {}, inputs or {}, False, False, **kwargs)


class TownRightsRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = load_automation_rules(RULES_FILE)
        cls.models = cached_game_data()[0]

    def vm(self, building, model=None):
        vm = RightsVM({building: model or self.models[building]}, self.rules)
        vm.building = building
        return vm

    def test_every_output_right_matches_only_its_outputs_across_building_generations(self):
        for right, goods in OUTPUT_RIGHTS.items():
            for good in goods:
                for name in ('old_workshop', 'new_factory'):
                    with self.subTest(right=right, good=good, building=name):
                        model = BuildingProduction(name, ((method({good: 2}),),))
                        vm = self.vm(name, model)
                        self.assertEqual(vm.score(), 0)
                        vm.town_rights.add(right)
                        self.assertEqual(vm.score(), 500)
                        vm.town_rights = {'municipia_privilegia', 'nuremberg_rights_town_rights'}
                        self.assertEqual(vm.score(), 0)

    def test_weighted_multioutput_union_is_not_quantity_sum_or_right_count(self):
        model = BuildingProduction('mixed', ((method({'dyes': 1, 'tools': 9}),),))
        vm = self.vm('mixed', model)
        vm.base_prices = {'dyes': 9, 'tools': 1}
        vm.town_rights = {'royal_textile_rights', 'royal_book_rights'}
        self.assertEqual(vm.score(), 250)
        vm.prices = {'dyes': 1000, 'tools': .01}
        self.assertEqual(vm.score(), 250)  # market prices never redefine intent
        vm.town_rights.add('royal_tooling_rights')
        self.assertEqual(vm.score(), 500)

    def test_multiple_slots_and_unavailable_alternative(self):
        first = method({'tools': 1}, {'iron': 1})
        locked = method({'cloth': 1}, unlock_advances=('textile_tech',))
        model = BuildingProduction('mixed', ((locked, first), (method({'cloth': 1}),)))
        vm = self.vm('mixed', model)
        vm.town_rights = {'royal_textile_rights'}
        self.assertEqual(vm.score(), 250)
        vm.advances.add('textile_tech')
        self.assertEqual(vm.score(), 500)

    def test_recipe_supply_selection_and_gates_are_preserved(self):
        model = BuildingProduction('mixed', ((
            method({'tools': 1}, {'iron': 1}), method({'cloth': 1}, {'wool': 1}),
        ),))
        vm = self.vm('mixed', model)
        vm.town_rights = {'royal_tooling_rights'}
        self.assertEqual(vm.score(), 500)
        vm.short_goods = {'iron'}
        self.assertEqual(vm.score(), 0)  # now selects the cloth method
        vm = self.vm('only_tools', BuildingProduction('only_tools', ((method({'tools': 1}, {'iron': 1}),),)))
        vm.short_goods = {'iron'}
        vm.town_rights = {'royal_tooling_rights'}
        self.assertEqual(vm.score(), 500)
        self.assertFalse(vm.available())  # preference cannot bypass the input gate

    def test_consumption_does_not_match_and_no_output_is_safe(self):
        for outputs in ({}, {'paper': 2}, {'tools': 0}):
            vm = self.vm('consumer', BuildingProduction('consumer', ((method(outputs, {'tools': 1}),),)))
            vm.town_rights = {'royal_tooling_rights'}
            self.assertEqual(vm.score(), 0)

    def test_native_preference_zero_five_ten_and_addition(self):
        vm = self.vm('tools_guild')
        vm.town_rights = {'royal_tooling_rights'}
        vm.raw_goods = set().union(*(set(m.raw_inputs) for s in self.models['tools_guild'].slots for m in s))
        vm.native_values.update({'scope:eu5ab_candidate_location.market_access': 1,
                                 'scope:eu5ab_candidate_location.local_control': 1})
        for priority in (0, 5, 10):
            vm.variables['eu5ab_global_native_input_priority'] = priority
            self.assertEqual(vm.score(), 500)
            self.assertEqual(vm.score() + vm.value('eu5ab_native_input_fit_proxy_score'), 500 + priority * 50)

    def test_actual_guild_and_successor_outputs(self):
        for name in ('cloth_guild', 'tools_guild', 'tools_workshop'):
            vm = self.vm(name)
            vm.town_rights = {'royal_textile_rights', 'royal_tooling_rights'}
            self.assertEqual(vm.score(), 500)
        for building, rights in BUILDING_RIGHTS.items():
            vm = self.vm(building)
            vm.town_rights = set(rights) | {'royal_textile_rights', 'royal_jewelry_rights'}
            self.assertEqual(vm.score(), 500)
        vm = self.vm('cloth_factory', BuildingProduction('cloth_factory', ((method({'cloth': 1}),),)))
        vm.town_rights = {'flemish_cloth_industries_right'}
        self.assertEqual(vm.score(), 0)  # guild cap does not apply to later factories

    def test_local_rights_do_not_leak_between_locations(self):
        vm = self.vm('tools_guild')
        vm.town_rights = {'royal_tooling_rights'}
        self.assertEqual(vm.score(), 500)
        vm.town_rights = set()  # next candidate location in the same province
        self.assertEqual(vm.score(), 0)

    def test_no_rights_skip_prices_and_zero_value_output_is_safe(self):
        vm = self.vm('tools_guild')
        vm.base_prices = {'tools': 0}
        vm.town_rights = {'royal_tooling_rights'}
        self.assertEqual(vm.score(), 0)
        vm.town_rights.clear()
        # Reading the denominator would divide by a sentinel, exposing accidental work.
        vm.native_values['eu5ab_town_rights_tools_guild_total'] = -1
        self.assertEqual(vm.score(), 0)
        self.assertEqual(vm.native_queries, [])

    def test_snapshot_uses_native_any_rights_guard_and_building_switch(self):
        effect = render_town_rights_effects(self.models, self.rules)
        body = parse(effect)[0][2]
        guarded = next(value for key, _, value in body if key == 'if')
        limit = next(value for key, _, value in guarded if key == 'limit')
        self.assertIn(('has_any_town_rights', '=', 'yes'),
                      next(value for key, _, value in limit
                           if key == 'scope:eu5ab_candidate_location'))
        switch = next(value for key, _, value in guarded if key == 'switch')
        cases = {key: value for key, _, value in switch}
        self.assertEqual(cases['trigger'], 'this')

        def rights(entries):
            found = set()
            for key, _, value in entries:
                if key == 'has_town_rights':
                    found.add(value.removeprefix('town_rights_type:'))
                elif isinstance(value, list):
                    found.update(rights(value))
            return found

        self.assertEqual(rights(cases['building_type:tools_guild']),
                         {'royal_tooling_rights', 'scandinavian_bergslag_privileges'})
        self.assertNotIn('this = building_type:', effect)

    def test_prepared_score_matches_live_and_zero_cache_is_ready(self):
        model = BuildingProduction('mixed', ((method({'dyes': 1, 'tools': 9}),),))
        vm = self.vm('mixed', model)
        vm.base_prices = {'dyes': 9, 'tools': 1}
        for town_rights, expected in ((set(), 0), ({'royal_textile_rights'}, 250),
                                      ({'royal_tooling_rights'}, 250),
                                      ({'royal_textile_rights', 'royal_tooling_rights'}, 500),
                                      ({'market_charter'}, 0)):
            with self.subTest(town_rights=town_rights):
                vm.town_rights = set(town_rights)
                for name in (SCORE_CACHE, SCORE_CACHE_BUILDING, SCORE_CACHE_READY):
                    vm.variables.pop(name, None)
                self.assertEqual(vm.score(), expected)
                vm.prepare_town_rights_score()
                self.assertEqual(vm.score(), expected)
                self.assertEqual(vm.variables[SCORE_CACHE_BUILDING], 'building_type:mixed')
                self.assertIn(SCORE_CACHE_READY, vm.variables)
                if expected == 0:
                    self.assertNotIn(SCORE_CACHE, vm.variables)

    def test_food_boosters_need_real_demand(self):
        vm = self.vm('windmill')
        vm.town_rights = set(FOOD_RIGHTS)
        self.assertEqual(vm.score(), 0)
        vm.demands.add('eu5ab_windmill_output_demand')
        self.assertEqual(vm.score(), 500)
        vm = self.vm('forest_village')
        vm.town_rights = set(FOOD_RIGHTS)
        self.assertEqual(vm.score(), 500)

    def test_rendered_template_and_rgo_scoring_integration(self):
        policies = load_policies(POLICY_FILE)
        recipes, demands, upgrades, workforce = cached_game_data()
        text = render_needs_script_values(policies, load_building_catalog(CATALOG_FILE),
                                         self.rules, recipes, workforce, upgrades, demands)
        definitions = {k: v for k, _, v in parse(text)}
        names = [f'eu5ab_score_{p.id}' for p in policies]
        names += [f'eu5ab_score_template_slot_{s}' for s in TEMPLATE_SLOTS]
        names += ['eu5ab_score_custom_template']
        for name in names:
            body = definitions[name]
            self.assertEqual(body.count(('add', '=', 'eu5ab_town_rights_candidate_score')), 1, name)
            self.assertEqual(body.count(('add', '=', 'eu5ab_industry_candidate_score')), 1, name)
            self.assertEqual(body.count(('add', '=', 'eu5ab_native_input_fit_proxy_score')), 1, name)
        self.assertEqual(definitions['eu5ab_rgo_candidate_score'].count(
            ('add', '=', 'eu5ab_town_rights_rgo_score')), 1)
        self.assertNotIn(('add', '=', 'eu5ab_industry_candidate_score'), definitions['eu5ab_rgo_candidate_score'])
        vm = self.vm('tools_guild')
        vm.definitions.update(definitions)
        vm.native_values.update({
            'eu5ab_universal_need_score': 100,
            'eu5ab_recipe_economic_efficiency_score': 20,
            'eu5ab_native_input_fit_proxy_score': 250,
            'eu5ab_industry_candidate_score': 0,
        })
        vm.variables['eu5ab_global_pause_low_workforce'] = 1
        self.assertEqual(vm.value('eu5ab_score_custom_template'), 370)
        vm.town_rights = {'royal_tooling_rights'}
        self.assertEqual(vm.value('eu5ab_score_custom_template'), 870)
        vm.native_values['eu5ab_industry_candidate_score'] = 500
        self.assertEqual(vm.value('eu5ab_score_custom_template'), 1370)

    def test_rgo_expansion_caps_and_goods(self):
        vm = self.vm('tools_guild')
        for right in RGO_RIGHTS:
            vm.town_rights = {right}
            self.assertEqual(vm.value('eu5ab_town_rights_rgo_score'), 500)
        vm.town_rights = {'royal_book_rights', 'royal_textile_rights'}
        vm.raw_goods = {'dyes'}
        self.assertEqual(vm.value('eu5ab_town_rights_rgo_score'), 500)
        vm.raw_goods = {'iron'}
        self.assertEqual(vm.value('eu5ab_town_rights_rgo_score'), 0)
        vm.town_rights.update(RGO_RIGHTS)
        vm.full_rgo = True
        self.assertEqual(vm.value('eu5ab_town_rights_rgo_score'), 0)

    def test_food_storage_and_actual_production_are_distinct(self):
        vm = RightsVM({b: self.models[b] for b in ('granary', 'village_granary')}, self.rules)
        for building in ('granary', 'village_granary'):
            vm.building = building
            for storage_demand, saved, rights, expected in (
                (False, 0, STORAGE_RIGHTS, 0),
                (True, 0, STORAGE_RIGHTS, 500),
                (False, 2, STORAGE_RIGHTS, 500),
                (False, 2, FOOD_RIGHTS, 0),
            ):
                with self.subTest(building=building, storage_demand=storage_demand,
                                  saved=saved, rights=rights):
                    vm.demands = {'eu5ab_granary_storage_demand'} if storage_demand else set()
                    vm.native_values['eu5ab_granary_monthly_food_saved'] = saved
                    vm.town_rights = set(rights)
                    # A previous candidate's score must not be read for the
                    # other building type, including a cached zero score.
                    other = 'village_granary' if building == 'granary' else 'granary'
                    vm.variables[SCORE_CACHE_BUILDING] = 'building_type:' + other
                    vm.variables[SCORE_CACHE_READY] = True
                    vm.variables[SCORE_CACHE] = 500 - expected
                    self.assertEqual(vm.score(), expected)
                    vm.prepare_town_rights_score()
                    self.assertEqual(vm.score(), expected)
                    self.assertEqual(vm.variables[SCORE_CACHE_BUILDING], 'building_type:' + building)
        vm = self.vm('farm', BuildingProduction('farm', ((method({'wheat': 1}),),)))
        vm.town_rights = set(STORAGE_RIGHTS)
        self.assertEqual(vm.score(), 0)
        vm.town_rights = set(FOOD_RIGHTS)
        self.assertEqual(vm.score(), 500)
        vm = self.vm('irrigation_systems')
        vm.town_rights = set(FOOD_RIGHTS)
        vm.demands.add('eu5ab_irrigation_food_demand')
        vm.native_values['raw_material_output'] = 2
        vm.raw_goods = {'iron'}
        self.assertEqual(vm.score(), 0)
        vm.raw_goods = {'wheat'}
        self.assertEqual(vm.score(), 500)
        vm.native_values['raw_material_output'] = 0
        self.assertEqual(vm.score(), 0)


class InstalledTownRightsTests(unittest.TestCase):
    def test_reviewed_mapping_matches_installed_vanilla_modifiers(self):
        root = Path('E:/SteamLibrary/steamapps/common/Europa Universalis V/game/in_game/common/town_rights')
        if not root.is_dir():
            self.skipTest('Installed EU5 required for source mapping audit')
        definitions = {k: dict(script_blocks(body)).get('location_modifier', '')
                       for path in root.glob('*.txt')
                       for k, body in script_blocks(path.read_text(encoding='utf-8-sig'))}
        extracted_outputs = {
            right: set(re.findall(r'local_([a-z_]+)_output_modifier\s*=\s*0\.[1-9]', body))
            for right, body in definitions.items()
            if re.search(r'local_[a-z_]+_output_modifier\s*=\s*0\.[1-9]', body)
        }
        self.assertEqual(extracted_outputs, {r: set(g) for r, g in OUTPUT_RIGHTS.items()})
        self.assertEqual(set(RGO_RIGHTS), {r for r, b in definitions.items() if 'local_max_rgo_size_modifier' in b})
        self.assertEqual(set(FOOD_RIGHTS), {r for r, b in definitions.items() if 'local_monthly_food_modifier' in b})
        self.assertEqual(set(STORAGE_RIGHTS), {r for r, b in definitions.items() if 'local_food_capacity' in b})
        for right, goods in OUTPUT_RIGHTS.items():
            for good in goods:
                self.assertRegex(definitions[right], rf'local_{good}_output_modifier\s*=\s*0\.[1-9]')
        for building, rights in BUILDING_RIGHTS.items():
            for right in rights:
                self.assertRegex(definitions[right], rf'local_{building}_building_levels\s*=\s*[1-9]')
        for right in RGO_RIGHTS:
            self.assertIn('local_max_rgo_size_modifier', definitions[right])
        for right in FOOD_RIGHTS:
            self.assertIn('local_monthly_food_modifier', definitions[right])
        for right in STORAGE_RIGHTS:
            self.assertIn('local_food_capacity', definitions[right])
