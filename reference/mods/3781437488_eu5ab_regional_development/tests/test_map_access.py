"""Execute missing-map consumers with a native lookup that rejects absence."""
from copy import deepcopy
import unittest

from src.eu5autobuild.map_access import guard_map_membership
from src.eu5autobuild.production_goods import map_value
from src.eu5autobuild.script_syntax import parse, render
from tests._generated import generated_fixture
from tests._governor_script_vm import GovernorScriptVM


class StrictMaps(GovernorScriptVM):
    def __init__(self):
        super().__init__({}, {}, {}, {}, (), (), None)
        self.maps = {'country': {}, 'location': {}}
        self.owners = {'location': 'country'}
        self.lookups = 0

    def test(self, key, op, value, stack):
        if key == 'owner' and isinstance(value, list):
            return self.condition(value, stack + [self.owners[stack[-1]]])
        if key == 'is_key_in_variable_map':
            fields = {k: v for k, _, v in value}
            if fields['name'] not in self.maps[stack[-1]]:
                raise AssertionError('Native lookup on absent map')
            self.lookups += 1
            return self.target(fields['target'], stack) in self.maps[stack[-1]][fields['name']]
        return super().test(key, op, value, stack)


def lower_definitions(definitions):
    """Apply the same final pass to source fragments loaded by runtime VMs."""
    return {k: v for k, _, v in parse(guard_map_membership(render(
        [(name, '=', body) for name, body in definitions.items()])))}


class MapAccessTests(unittest.TestCase):
    def test_absent_empty_missing_and_present_zero_keep_membership_semantics(self):
        source = 'is_key_in_variable_map = { name = eu5ab_test target = this }'
        body = parse(guard_map_membership(source))
        for rows, expected, queries in ((None, False, 0), ({}, False, 0),
                                       ({'other': 3}, False, 1),
                                       ({'country': 0}, True, 1),
                                       ({'country': -2}, True, 1)):
            with self.subTest(rows=rows):
                vm = StrictMaps()
                if rows is not None:
                    vm.maps['country']['eu5ab_test'] = rows
                before = deepcopy(vm.maps)
                self.assertEqual(vm.condition(body, ['country']), expected)
                self.assertEqual(vm.lookups, queries)
                self.assertEqual(vm.maps, before)

    def test_negation_eager_boolean_and_prev_scope_preserve_cache_misses(self):
        source = '''owner = { OR = {
            NOT = { is_key_in_variable_map = { name = eu5ab_test target = prev } }
            AND = { is_key_in_variable_map = { name = eu5ab_test target = prev } }
        } }'''
        body = parse(guard_map_membership(source))
        vm = StrictMaps()
        self.assertTrue(vm.condition(body, ['location']))
        self.assertEqual(vm.lookups, 0)
        vm.maps['country']['eu5ab_test'] = {'location': 7}
        self.assertTrue(vm.condition(body, ['location']))
        self.assertEqual(vm.lookups, 2)

    def test_lexical_lowering_preserves_comments_strings_and_zero_reader(self):
        opaque = '# is_key_in_variable_map = { name = ignored }\nlabel = "is_key_in_variable_map = { name = ignored }"\n'
        self.assertEqual(guard_map_membership(opaque), opaque)
        source = 'eu5ab_value = ' + map_value('eu5ab_test', 'prev')
        guarded = parse(guard_map_membership(source))
        body = guarded[0][2]
        self.assertEqual(body[0], ('value', '=', '0'))
        condition = body[1][2][0][2]
        self.assertEqual(body[1][2][1], ('add', '=', '"variable_map(eu5ab_test|prev)"'))
        vm = StrictMaps()
        self.assertFalse(vm.condition(condition, ['location', 'country']))
        self.assertEqual(vm.lookups, 0)

    def test_all_generated_membership_checks_are_conditionally_protected(self):
        fixture = generated_fixture()
        checked = 0
        def visit(entries, allowed=()):
            nonlocal checked
            for key, _, value in entries:
                if key == 'is_key_in_variable_map':
                    name = dict((k, v) for k, _, v in value)['name']
                    self.assertIn(name, allowed)
                    checked += 1
                elif key == 'trigger_if':
                    limit = next(v for k, _, v in value if k == 'limit')
                    proof = tuple(v for k, _, v in limit if k == 'has_variable_map')
                    visit(limit, allowed)
                    visit([e for e in value if e[0] != 'limit'], proof)
                elif isinstance(value, list):
                    # A scope change cannot inherit another scope's map proof.
                    visit(value, allowed if key in ('AND', 'OR', 'NOT') else ())
        for source in (fixture.effects, fixture.triggers, fixture.values, fixture.scripted_guis):
            visit(parse(source))
        self.assertGreater(checked, 0)

    def test_worker_unknown_and_dropped_zero_keep_real_fallbacks(self):
        from src.eu5autobuild.worker_screening import render_effects, predicate_wrapper, value_wrapper, prepare, mapping
        from tests.test_worker_screening_runtime import WorkerVM
        from tests.test_candidate_collection_runtime import CandidateCollectionRuntimeTests
        source = render_effects() + predicate_wrapper('eu5ab_inputs_available', 'inputs')
        source += value_wrapper('eu5ab_output_price_factor_live', 'output_price_factor')
        definitions = {k: v for k, _, v in parse(guard_map_membership(source))}
        class VM(WorkerVM):
            def test(self, k, op, v, stack):
                if k == 'is_key_in_variable_map':
                    name = dict((a, c) for a, _, c in v)['name']
                    if name not in self.maps[stack[-1]]:
                        raise AssertionError('Worker checked absent map')
                return super().test(k, op, v, stack)
        rows = CandidateCollectionRuntimeTests.rows(count=1)
        rows['building_0'].update(inputs=True, pending_ready=False, price_valid=True, output=0)
        vm = VM(definitions, rows)
        vm.scopes.update(eu5ab_candidate_location='location', eu5ab_candidate_building='building_0')
        self.assertTrue(vm.test('eu5ab_inputs_available', '=', 'yes', ['building_0']))
        self.assertEqual(vm.queries[('eu5ab_inputs_available', 'building_0')], 1)
        vm.execute(definitions[prepare('inputs')], ['building_0'])
        count = vm.queries.copy()
        self.assertTrue(vm.test('eu5ab_inputs_available', '=', 'yes', ['building_0']))
        self.assertEqual(vm.queries, count)
        vm.execute(definitions[prepare('pending_ready')], ['building_0'])
        self.assertEqual(vm.maps['location'][mapping('pending_ready')]['building_0'], 3)
        vm.maps['location'][mapping('output_price_factor_ready')] = {'building_0': 1}
        self.assertEqual(vm.value('eu5ab_output_price_factor_live', ['building_0']), 0)
        self.assertNotIn(mapping('output_price_factor'), vm.maps['location'])

    def test_production_recipe_first_write_release_and_cooldown_with_absent_maps(self):
        from tests.test_production_cohorts_runtime import CohortVM
        class VM(CohortVM):
            def test(self, k, op, v, stack):
                if k == 'is_key_in_variable_map':
                    name = dict((a, c) for a, _, c in v)['name']
                    if name not in self.variable_maps.get(stack[-1], {}):
                        raise AssertionError('Production checked absent map: ' + name)
                return super().test(k, op, v, stack)
        vm = VM()
        for field in ('definitions', 'capacity_values', 'capacity_triggers'):
            setattr(vm, field, lower_definitions(getattr(vm, field)))
        ident = vm.start()
        vm.observe(0, 1)
        self.assertGreater(vm.pending(), 0)
        self.assertEqual(vm.record(ident, 'state'), 0)
        vm.observe(1, 0, workers=1000)
        self.assertEqual(vm.record(ident, 'released'), 1)
        self.assertEqual(vm.pending(), 0)
        deadline = vm.deadline(ident)
        self.assertGreater(deadline, 0)
        vm.run('eu5ab_pf_rebuild_goods_index', vm.ROOT)
        vm.observe(1, 0, workers=1000)
        self.assertEqual(vm.deadline(ident), deadline)


if __name__ == '__main__':
    unittest.main()
