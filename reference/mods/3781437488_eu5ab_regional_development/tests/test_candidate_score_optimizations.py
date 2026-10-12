"""Execute generated score branches against their current rule contracts.

Vanilla market predicates and building levels are injected. This verifies the
generated routing and arithmetic, not the game's engine query implementation.
"""
from itertools import product
import re
import unittest

from src.eu5autobuild.governor_connections import bundled_straits
from src.eu5autobuild.generator import (
    CATALOG_FILE, POLICY_FILE, RULES_FILE, TEMPLATE_SLOTS,
    _catalog_building_ids, _policy_index, generated_files, ROOT,
)
from src.eu5autobuild.policy import load_building_catalog, load_policies
from src.eu5autobuild.rules import load_automation_rules
from tests._game_data_fixtures import cached_game_data
from tests._governor_script_vm import parse


class ScoreVM:
    def __init__(self, definitions, triggers):
        self.definitions, self.triggers = definitions, triggers
        self.building = 'unknown'
        self.variables = {'eu5ab_template_slot': 1}
        self.variable_maps = {}
        self.short_goods = set()
        self.market_queries = []
        self.level = 0
        self.native_values = {}
        self.native_queries = []
        self.raw_material = 'unknown'
        self.town_rights = set()

    def value(self, value):
        if isinstance(value, list):
            return self.run(value)
        if value.startswith(('building_type:', 'goods:')):
            return value
        if value in self.native_values:
            self.native_queries.append(value)
            return self.native_values[value]
        if value == 'raw_material_output':
            return 0
        if value in self.definitions:
            return self.run(self.definitions[value])
        if '.var:' in value:
            return self.variables.get(value.split('.var:')[1], 0)
        if value.startswith('var:'):
            return self.variables.get(value[4:], 0)
        if value.startswith('variable_map('):
            name, _ = value[len('variable_map('):-1].split('|')
            return self.variable_maps.get(name, {}).get(f'building_type:{self.building}', 0)
        if '.location_building_level(' in value:
            if f'building_type:{self.building})' not in value:
                raise AssertionError("Unsupported script input: f'building_type:{self.building})' in value")
            return self.level
        return float(value)

    def condition(self, entries):
        return all(self.predicate(key, op, value) for key, op, value in entries)

    def predicate(self, key, op, value):
        if key == 'AND':
            return self.condition(value)
        if key == 'raw_material':
            return value == f'goods:{self.raw_material}'
        if key == 'has_town_rights':
            return value.removeprefix('town_rights_type:') in self.town_rights
        if key == 'has_any_town_rights':
            return bool(self.town_rights) == (value == 'yes')
        if key == 'OR':
            return any(self.predicate(*entry) for entry in value)
        if key == 'NOT':
            return not self.condition(value)
        if key == 'this':
            return value == f'building_type:{self.building}'
        if key == 'always':
            return value == 'yes'
        if key == 'has_variable':
            return value in self.variables
        if key == 'has_variable_map':
            return bool(self.variable_maps.get(value))
        if key == 'trigger_if':
            limit = next(body for name, _, body in value if name == 'limit')
            return not self.condition(limit) or self.condition(
                [entry for entry in value if entry[0] != 'limit'])
        if key == 'is_key_in_variable_map':
            fields = {k: v for k, _, v in value}
            return f'building_type:{self.building}' in self.variable_maps.get(fields['name'], {})
        if key == 'exists' and value.startswith('var:'):
            return value[4:] in self.variables
        if key == 'scope:eu5ab_candidate_location':
            return self.condition(value)
        if key == 'scope:eu5ab_candidate_location.market':
            # Treat each unchanged vanilla predicate as an injected boolean.
            if not (op == '?='):
                raise AssertionError("Unsupported script input: op == '?='")
            query, comparator, _ = value[0]
            if not (comparator == '<'):
                raise AssertionError("Unsupported script input: comparator == '<'")
            good = re.search(r'goods:([a-z_]+)', query)[1]
            self.market_queries.append(good)
            return good in self.short_goods
        if key == 'switch':
            cases = {k: v for k, _, v in value}
            if not (cases['trigger'] == 'this'):
                raise AssertionError("Unsupported script input: cases['trigger'] == 'this'")
            return self.condition(cases.get(f'building_type:{self.building}', cases['fallback']))
        if key in self.triggers:
            if not (value == 'yes'):
                raise AssertionError("Unsupported script input: value == 'yes'")
            return self.condition(self.triggers[key])
        if key == 'eu5ab_candidate_replaces_existing_building':
            return bool(self.native_values.get(key, False)) == (value == 'yes')
        left, right = self.value(key), self.value(value)
        if op == '=':
            return left == right
        if op == '>':
            return left > right
        if op == '>=':
            return left >= right
        if op == '<=':
            return left <= right
        if op == '<':
            return left < right
        raise AssertionError((key, op))

    def run(self, entries, result=0):
        matched = False
        for key, _, value in entries:
            if key in ('if', 'else_if', 'else'):
                if key == 'if':
                    matched = False
                if not matched and (key == 'else' or self.condition(value[0][2])):
                    result = self.run(value if key == 'else' else value[1:], result)
                    matched = True
            elif key == 'value':
                result = self.value(value)
            elif key == 'add':
                result += self.value(value)
            elif key == 'subtract':
                result -= self.value(value)
            elif key == 'multiply':
                result *= self.value(value)
            elif key == 'scope:eu5ab_candidate_location':
                result = self.run(value, result)
            elif key == 'divide':
                result /= self.value(value)
            elif key == 'min':
                result = max(result, self.value(value))
            elif key == 'max':
                result = min(result, self.value(value))
            elif key == 'switch':
                fields = {k: v for k, _, v in value}
                self.assert_switch_trigger(fields)
                result = self.run(fields.get('building_type:' + self.building, fields.get('fallback', [])), result)
            else:
                raise AssertionError(key)
            result = self.normalize_arithmetic(result)
        return result

    def normalize_arithmetic(self, result):
        return result

    @staticmethod
    def assert_switch_trigger(fields):
        if fields['trigger'] != 'this':
            raise AssertionError(fields['trigger'])


class CandidateScoreOptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_building_catalog(CATALOG_FILE)
        cls.rules = load_automation_rules(RULES_FILE)
        cls.policies = load_policies(POLICY_FILE)
        recipes, demands, upgrades, workforce = cached_game_data()
        files = generated_files(cls.policies, cls.catalog, cls.rules,
                                recipes=recipes, construction_demands=demands,
                                upgrades=upgrades, workforce=workforce, straits=bundled_straits())
        cls.values = {k: v for k, _, v in parse(files[ROOT / 'in_game/common/script_values/eu5ab_script_values.txt'])}
        cls.triggers = {k: v for k, _, v in parse(files[ROOT / 'in_game/common/scripted_triggers/eu5ab_scripted_triggers.txt'])}
        cls.effects = {k: v for k, _, v in parse(files[ROOT / 'in_game/common/scripted_effects/eu5ab_scripted_effects.txt'])}
    def test_disabled_native_preference_skips_all_fit_queries(self):
        for absent in (False, True):
            vm = ScoreVM(self.values, self.triggers)
            if not absent:
                vm.variables['eu5ab_global_native_input_priority'] = 0
            vm.native_values.update({
                'eu5ab_native_input_fit_unscaled': 123.45,
                'scope:eu5ab_candidate_location.market_access': 0.8,
                'scope:eu5ab_candidate_location.local_control': 0.6,
                'eu5ab_native_input_shortage_factor': 0.5,
            })
            self.assertEqual(vm.value('eu5ab_native_input_fit_proxy_score'), 0)
            self.assertEqual(vm.native_queries, [])

    def test_nonzero_native_preference_preserves_arithmetic_and_queries(self):
        # Preserve negative/out-of-range inputs too, rather than silently clamping.
        for priority, unscaled, access, control, shortage in product(
            (-2, 0.25, 1, 5, 10, 11), (0, 1.2345, 100),
            (0, 0.45, 1), (0, 0.7, 1), (0.5, 1),
        ):
            vm = ScoreVM(self.values, self.triggers)
            vm.variables['eu5ab_global_native_input_priority'] = priority
            vm.native_values.update({
                'eu5ab_native_input_fit_unscaled': unscaled,
                'scope:eu5ab_candidate_location.market_access': access,
                'scope:eu5ab_candidate_location.local_control': control,
                'eu5ab_native_input_shortage_factor': shortage,
            })
            with self.subTest(priority=priority, unscaled=unscaled, access=access,
                              control=control, shortage=shortage):
                expected = unscaled * priority / 10 * access * control * shortage
                self.assertAlmostEqual(vm.value('eu5ab_native_input_fit_proxy_score'), expected)
                self.assertEqual(vm.native_queries, [
                    'eu5ab_native_input_fit_unscaled',
                    'scope:eu5ab_candidate_location.market_access',
                    'scope:eu5ab_candidate_location.local_control',
                    'eu5ab_native_input_shortage_factor',
                ])

    def test_current_worker_factor_does_not_read_forecast_or_strategic_need(self):
        for strict, workers, jobs, need in product(
            (0, 1), (0, 99.999, 100, 100.001, 150), (0, 100), (-10, 0, 10),
        ):
            vm = ScoreVM(self.values, self.triggers)
            vm.variables['eu5ab_global_pause_low_workforce'] = strict
            vm.native_values.update({
                'eu5ab_candidate_current_available_workers': workers,
                'eu5ab_candidate_net_new_jobs': jobs,
                'eu5ab_universal_need_score': need,
            })
            with self.subTest(strict=strict, workers=workers, jobs=jobs, need=need):
                expected = 0.4 if strict == 0 and workers < jobs else 1
                self.assertAlmostEqual(vm.value('eu5ab_candidate_current_labor_factor'), expected)
                self.assertNotIn('eu5ab_universal_need_score', vm.native_queries)
                self.assertNotIn('eu5ab_candidate_projected_available_workers', vm.native_queries)

    def test_monthly_worker_factor_survives_collection_cleanup_and_skips_later_reads(self):
        vm = ScoreVM(self.values, self.triggers)
        vm.building = 'workshop'
        vm.variable_maps['eu5ab_batch_labor_factor'] = {'building_type:workshop': 0.4}
        vm.native_values.update(eu5ab_candidate_current_available_workers=1000, eu5ab_candidate_net_new_jobs=1)
        self.assertEqual(vm.value('eu5ab_candidate_current_labor_factor'), 0.4)
        self.assertEqual(vm.native_queries, [])
        cleanup = self.effects['eu5ab_clear_candidate_collection_cache']
        self.assertNotIn(('clear_variable_map', '=', 'eu5ab_batch_labor_factor'), cleanup)

    def test_source_score_matches_original_for_every_origin_and_building(self):
        from tests.test_production_runtime import ProductionVM
        models = cached_game_data()[0]
        vm = ProductionVM(models, self.rules)
        vm.definitions.update(self.values)
        vm.triggers.update(self.triggers)
        for index, policy in enumerate(self.policies):
            origin = int(_policy_index(policy, index))
            for building, definition in self.catalog.buildings.items():
                vm.building = building
                vm.variables['eu5ab_scan_preset_origin'] = origin
                # Policy preference must follow the same selected output as
                # pricing, including buildings with alternative output goods.
                outputs = set()
                for i, slot in enumerate(models[building].slots if building in models else ()):
                    selected = int(vm.value(f'eu5ab_recipe_{building}_{i}_selected'))
                    if selected:
                        outputs.update(slot[selected - 1].outputs)
                expected = next((max(0, self.rules.scores.policy_priority_base - rank * self.rules.scores.policy_priority_step)
                                 for rank, good in enumerate(policy.priority_goods)
                                 if good in outputs), 0)
                if building in self.rules.building_groups.get(policy.role, ()):
                    expected += self.rules.scores.role_match
                self.assertEqual(vm.value('eu5ab_copied_preset_origin_score'), expected, (origin, building))
        for origin in (0, -1, 999):
            vm.variables['eu5ab_scan_preset_origin'] = origin
            self.assertEqual(vm.value('eu5ab_copied_preset_origin_score'), 0)

    def test_origin_cache_zero_uncached_slots_and_scan_cleanup(self):
        vm = ScoreVM(self.values, self.triggers)
        for slot in TEMPLATE_SLOTS:
            vm.variables['eu5ab_template_slot'] = slot
            vm.variables[f'eu5ab_tpl_{slot}_preset_origin'] = slot + 100
            self.assertEqual(vm.value('eu5ab_current_preset_origin'), slot + 100)
        vm.variables['eu5ab_scan_preset_origin'] = 0
        self.assertEqual(vm.value('eu5ab_current_preset_origin'), 0)
        vm.variables.pop('eu5ab_scan_preset_origin')
        vm.variables['eu5ab_template_slot'] = 999
        self.assertEqual(vm.value('eu5ab_current_preset_origin'), 0)
        policy = self.effects['eu5ab_try_construct_current_policy']
        clear = ('remove_variable', '=', 'eu5ab_scan_preset_origin')
        self.assertEqual(policy.count(clear), 2)
        self.assertEqual(policy[-1], clear)
        initialize = next(v for k, _, v in policy if k == 'if' and 'eu5ab_uncached_preset_origin' in str(v))
        self.assertLess(policy.index(clear), policy.index(('if', '=', initialize)))
        self.assertLess(policy.index(('if', '=', initialize)), next(i for i, (k, _, _) in enumerate(policy) if k == 'eu5ab_collect_current_candidate_pools'))
        self.assertNotIn(clear, self.effects['eu5ab_try_construct_current_input_source'])

    def test_recipe_shortage_preserves_threshold_and_applies_penalty_once(self):
        from tests.test_production_runtime import ProductionVM
        vm = ProductionVM(cached_game_data()[0], self.rules)
        universal = next(v for k, _, v in self.values['eu5ab_universal_need_score'] if k == 'else')
        penalties = [entry for entry in universal if 'eu5ab_candidate_scoring_input_shortage' in str(entry)]
        self.assertEqual(len(penalties), 1)
        for good in self.rules.input_goods:
            market = vm.triggers['eu5ab_recipe_short_' + good][0][2]
            query, op, arithmetic = market[0]
            self.assertEqual(op, '<')
            self.assertEqual(arithmetic, [('value', '=', f'goods_demand_in_market(goods:{good})'),
                                         ('multiply', '=', str(self.rules.thresholds.input_shortage_supply_ratio))])
        for building, short, blocked in (
            ('mason', {'stone'}, False), ('mason', {'stone', 'clay'}, True),
            ('tools_workshop', {'iron'}, True), ('tools_workshop', {'cotton'}, False),
        ):
            vm.building, vm.short_goods = building, short
            expected = self.rules.scores.input_shortage_penalty if blocked else 0
            self.assertEqual(vm.run(penalties), expected)

    def test_expansion_scale_uses_only_destination_levels_and_excludes_replacement(self):
        vm = ScoreVM(self.values, self.triggers)
        vm.triggers = dict(vm.triggers)
        vm.triggers.pop('eu5ab_candidate_replaces_existing_building')
        universal = next(v for k, _, v in self.values['eu5ab_universal_need_score'] if k == 'else')
        start = next(i for i, entry in enumerate(universal) if 'location_building_level(' in str(entry))
        branches = universal[start:]
        self.assertEqual(len(branches), 1)
        for building in [*_catalog_building_ids(self.catalog), 'unknown']:
            vm.building = building
            for level in (0, 1, 7, 25):
                vm.level = level
                expected = 0 if building == 'unknown' else level * self.rules.thresholds.expansion_bonus_per_level
                self.assertEqual(vm.run(branches), expected, (building, level))
                vm.native_values['eu5ab_candidate_replaces_existing_building'] = True
                self.assertEqual(vm.run(branches), 0)
                vm.native_values['eu5ab_candidate_replaces_existing_building'] = False
