"""Exercise generated candidate collection and cache behavior.

Native predicates/iteration order are injected; this is not an engine benchmark.
"""
from collections import Counter
from copy import deepcopy
import random
import unittest

from src.eu5autobuild.generator import CURRENT_INPUT_CANDIDATE_POOLS, FOOD_BUILDING_GATES, WORKER_DIAGNOSTIC_COUNTERS
from tests._generated import generated_fixture, _blocks_for_token
from tests._governor_script_vm import GovernorScriptVM, parse


NORMAL = 'eu5ab_collect_current_candidate_pools'
INPUT = 'eu5ab_collect_current_input_candidate_pools'
CLEAR = 'eu5ab_clear_candidate_collection_cache'


class CollectionVM(GovernorScriptVM):
    def __init__(self, definitions, rows, *, policy=100, active=True):
        self.definitions = definitions
        self.rows = deepcopy(rows)
        for row in self.rows.values():
            row.setdefault('capacity', True)
        self.owners = {'location': self.ROOT, 'other': self.ROOT}
        self.vars = {self.ROOT: {'eu5ab_global_pause_low_workforce': 1}}
        for location in self.owners:
            self.vars[location] = {'eu5ab_policy_id': policy, 'eu5ab_template_slot': 1}
            self.vars[location].update({'eu5ab_worker_' + counter: 0 for counter in WORKER_DIAGNOSTIC_COUNTERS})
            if active:
                self.vars[location]['eu5ab_scan_promotion_active'] = True
        self.vars.update({b: {} for b in rows})
        self.lists = {scope: {} for scope in self.vars}
        self.maps = {scope: {} for scope in self.vars}
        self.scopes, self.local = {}, {}
        self.operations = 0
        self.queries = Counter()

    def target(self, word, stack):
        if word.endswith('.owner'):
            return self.owners.get(self.target(word[:-6], stack))
        return super().target(word, stack)

    def value(self, word, stack):
        return super().value(word.strip('"') if isinstance(word, str) else word, stack)

    def test(self, k, op, v, stack):
        if k == 'employment_size':
            return self.rows[stack[-1]].get('employment', 1) > float(v)
        if k == 'is_key_in_variable_map':
            fields = {a: c for a, _, c in v}
            return self.value(fields['target'], stack) in self.maps[stack[-1]].get(fields['name'], {})
        if k == 'eu5ab_upstream_output_shortage_preliminary':
            return self.condition(self.definitions[k], stack) == (v == 'yes')
        if k == 'eu5ab_candidate_pending_data_ready':
            return self.rows[stack[-1]].get('pending_ready', True) == (v == 'yes')
        if k == 'eu5ab_candidate_base_eligible':
            return (self.test('eu5ab_candidate_is_latest_unlocked', '=', 'yes', stack)
                    and self.test('eu5ab_candidate_location_can_build', '=', 'yes', stack)) == (v == 'yes')
        predicates = {
            'eu5ab_current_building_allowed': 'allowed',
            'eu5ab_current_input_source_building_allowed': 'upstream_allowed',
            'eu5ab_current_special_building_allowed': 'special',
            'eu5ab_candidate_is_latest_unlocked': 'latest',
            'eu5ab_candidate_location_can_build': 'legal',
            'eu5ab_candidate_location_eligible': 'legal',
            'eu5ab_candidate_has_capacity': 'capacity',
            'eu5ab_upstream_output_shortage': 'shortage',
            'eu5ab_has_local_workforce': 'workforce',
            'eu5ab_inputs_available': 'inputs',
            'eu5ab_output_not_oversupplied': 'output',
            **{gate: gate for gate, _ in FOOD_BUILDING_GATES},
        }
        if k in predicates:
            building = stack[-1]
            self.queries[(k, building)] += 1
            result = self.rows[building][predicates[k]]
            if k == 'eu5ab_has_local_workforce' and self.vars[self.ROOT]['eu5ab_global_pause_low_workforce'] <= 0:
                result = True
            return result == (v == 'yes')
        kinds = {'eu5ab_candidate_is_upgrade': 'upgrade',
                 'eu5ab_candidate_has_existing_building': 'expansion',
                 'eu5ab_candidate_lacks_existing_building': 'new'}
        if k in kinds:
            self.queries[(k, stack[-1])] += 1
            return (self.rows[stack[-1]]['kind'] == kinds[k]) == (v == 'yes')
        # Preserve short circuiting so query counts measure the executed path.
        if k in ('AND', 'OR', 'NOT'):
            return (any(self.test(*e, stack) for e in v) if k == 'OR'
                    else not self.condition(v, stack) if k == 'NOT'
                    else self.condition(v, stack))
        if k == 'owner':
            return self.condition(v, stack + [self.owners[stack[-1]]])
        return super().test(k, op, v, stack)

    def execute(self, entries, stack):
        # Keep a whole if/else chain in a single base-VM invocation.
        index = 0
        while index < len(entries):
            k, _, v = entries[index]
            end = index + 1
            if k == 'if':
                while end < len(entries) and entries[end][0] in ('else_if', 'else'):
                    end += 1
            if k == 'owner':
                self.execute(v, stack + [self.owners[stack[-1]]])
            elif k == 'ordered_buildable_building_type':
                self.queries[('enumeration', self.scopes['eu5ab_candidate_location'])] += 1
                data = {a: c for a, _, c in v}
                pool = [b for b in self.rows if self.condition(data['limit'], stack + [b])]
                for building in pool[:int(data['max'])]:
                    self.execute([e for e in v if e[0] not in ('limit', 'max', 'check_range_bounds')], stack + [building])
            elif k in ('eu5ab_cache_candidate_promotion', 'eu5ab_clear_recipe_score_snapshot'):
                pass  # Promotion arithmetic is covered by workforce runtime tests.
            elif k in ('eu5ab_prepare_candidate_market_prices',
                       'eu5ab_prepare_candidate_upstream_market_cache'):
                pass  # Market snapshot behavior has a dedicated runtime test.
            elif k in ('eu5ab_prepare_current_normal_catalog', 'eu5ab_prepare_current_input_catalog'):
                kind = 'input' if '_input_' in k else 'normal'
                location = self.scopes['eu5ab_candidate_location']
                policy = self.vars[location]['eu5ab_policy_id']
                if policy == 100:
                    identity = f'template_{self.vars[location]["eu5ab_template_slot"]}'
                    kind, field = 'normal', 'allowed'
                else:
                    identity = f'policy_{policy}'
                    field = 'upstream_allowed' if kind == 'input' else 'allowed'
                name = f'eu5ab_active_{kind}_catalog_{identity}'
                if name not in self.lists[self.ROOT]:
                    self.queries[('enumeration', location)] += 1
                    self.lists[self.ROOT][name] = [
                        building for building, row in self.rows.items()
                        if row[field] and row['latest']
                    ]
            elif k.startswith('eu5ab_prepare_worker_screen_'):
                pass  # Injected gates here; real cache effects have their own VM.
            elif k == 'eu5ab_prepare_worker_location_eligibility':
                # The lazy legality effect is executed in worker-upgrade tests.
                location = self.scopes['eu5ab_candidate_location']
                self.vars[location].pop('eu5ab_worker_location_eligible', None)
                if self.test('eu5ab_candidate_location_eligible', '=', 'yes', stack):
                    self.vars[location]['eu5ab_worker_location_eligible'] = True
            elif k == 'eu5ab_evaluate_candidate_workforce':
                # Execute the real memoization around an injected native result.
                # The merged arithmetic is compared across the full catalog in
                # test_workforce_runtime, separately from collection control flow.
                self.queries[('workforce_evaluation', stack[-1])] += 1
                if self.rows[stack[-1]]['workforce']:
                    self.vars[self.scopes['eu5ab_candidate_location']]['eu5ab_candidate_workforce_passed'] = True
            else:
                super().execute(entries[index:end], stack)
            index = end

    def run(self, name, location='location'):
        self.execute(self.definitions[name], [location])

    def result(self, location='location'):
        return ({k: v for k, v in self.lists[location].items() if k.startswith('eu5ab_current_')},
                {k: v for k, v in self.vars[location].items() if k.startswith('eu5ab_worker_') or k == 'eu5ab_had_workforce_blocked_candidate'})


class CandidateCollectionRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        effects = generated_fixture().effects
        cls.definitions = {name: parse(_blocks_for_token(effects, '\n' + name + ' = ')[0])[0][2]
                           for name in (NORMAL, INPUT, CLEAR, 'eu5ab_prepare_candidate_workforce')}
        from src.eu5autobuild.worker_screening import render_effects
        cls.definitions.update({k: v for k, _, v in parse(render_effects())})
        name = 'eu5ab_prepare_candidate_collection_gate'
        cls.definitions[name] = parse(_blocks_for_token(effects, '\n' + name + ' = ')[0])[0][2]
        name = 'eu5ab_upstream_output_shortage_preliminary'
        cls.definitions[name] = parse(_blocks_for_token(generated_fixture().triggers, '\n' + name + ' = ')[0])[0][2]

    @staticmethod
    def rows(seed=0, count=40):
        rng = random.Random(seed)  # nosec B311: deterministic test fixture, not a secret
        rows = {}
        for i in range(count):
            fields = ('allowed', 'special', 'latest', 'legal', 'shortage', 'workforce', 'inputs', 'output',
                      *(gate for gate, _ in FOOD_BUILDING_GATES))
            row = {field: rng.random() > .15 for field in fields}
            row['upstream_allowed'] = row['allowed']
            # Collection receives a valid, roomy native snapshot by default.
            # Real capacity arithmetic and exemptions have their own runtime VM.
            row['capacity'] = True
            row['kind'] = ('upgrade', 'expansion', 'new')[i % 3]
            rows['building_' + str(i)] = row
        return rows

    def test_custom_cached_path_matches_pools_order_and_diagnostics(self):
        for seed in range(20):
            for pause in (0, 1):
                with self.subTest(seed=seed, pause=pause):
                    rows = self.rows(seed)
                    vm = CollectionVM(self.definitions, rows)
                    vm.vars[vm.ROOT]['eu5ab_global_pause_low_workforce'] = pause
                    vm.run(NORMAL)
                    vm.run(INPUT)
                    self.assertEqual(vm.queries[('enumeration', 'location')], 1)
                    for b in rows:
                        for gate in ('eu5ab_candidate_is_latest_unlocked', 'eu5ab_candidate_location_can_build'):
                            self.assertLessEqual(vm.queries[(gate, b)], 1)
                        self.assertLessEqual(vm.queries[('workforce_evaluation', b)], 1 if pause else 0)

    def test_gate_cache_matches_uncached_outcomes_and_preserves_per_pool_diagnostics(self):
        for seed in range(10):
            rows = self.rows(seed)
            cached = CollectionVM(self.definitions, rows)
            uncached = CollectionVM(self.definitions, rows, active=False)
            for vm in (cached, uncached):
                vm.run(NORMAL)
                vm.run(INPUT)
            self.assertEqual(cached.result(), uncached.result())
            for building in rows:
                for gate in ('eu5ab_candidate_has_capacity', *(k for k, _ in FOOD_BUILDING_GATES)):
                    self.assertLessEqual(cached.queries[(gate, building)], 1)
            self.assertLess(sum(cached.queries.values()), sum(uncached.queries.values()))
            cached.run(CLEAR)
            self.assertFalse(cached.maps['location'].get('eu5ab_candidate_collection_gates'))

    def test_upstream_unknown_waits_while_known_no_shortage_is_filtered(self):
        rows = self.rows(count=1)
        row = rows['building_0']
        row.update({field: True for field in row if field != 'kind'})
        row.update(shortage=False, kind='new')
        for ready in (True, False):
            row['pending_ready'] = ready
            vm = CollectionVM(self.definitions, rows)
            vm.run(INPUT)
            pool = vm.lists['location'].get('eu5ab_current_input_new_candidate_pool', [])
            self.assertEqual(pool, [] if ready else ['building_0'])

    def test_preset_keeps_upstream_only_buildings_and_standalone_falls_back(self):
        rows = self.rows(3)
        for row in rows.values():
            row['upstream_allowed'] = not row['allowed']
        for policy, active in ((1, True), (100, False)):
            vm = CollectionVM(self.definitions, rows, policy=policy, active=active)
            vm.run(NORMAL)
            vm.run(INPUT)
            self.assertEqual(vm.queries[('enumeration', 'location')], 2 if policy == 1 else 1)
            self.assertTrue(any(vm.lists['location'].get(name) for name in CURRENT_INPUT_CANDIDATE_POOLS))

    def test_empty_valid_cache_does_not_fall_back_and_other_location_isolated(self):
        rows = self.rows()
        for row in rows.values():
            row['legal'] = False
        vm = CollectionVM(self.definitions, rows)
        vm.run(NORMAL)
        vm.run(INPUT)
        self.assertEqual(vm.queries[('enumeration', 'location')], 1)
        vm.run(INPUT, 'other')
        # The country/template catalog is shared across locations.
        self.assertEqual(vm.queries[('enumeration', 'other')], 0)

    def test_changed_slot_and_cleared_cache_require_fresh_scan(self):
        vm = CollectionVM(self.definitions, self.rows())
        vm.run(NORMAL)
        vm.vars['location']['eu5ab_template_slot'] = 2
        vm.run(INPUT)
        self.assertEqual(vm.queries[('enumeration', 'location')], 2)
        vm.run(CLEAR)
        self.assertFalse(vm.lists['location']['eu5ab_candidate_base_pool'])
        self.assertNotIn('eu5ab_candidate_base_slot', vm.vars['location'])
        vm.run(INPUT)
        # Candidate cleanup does not invalidate the monthly country catalog.
        self.assertEqual(vm.queries[('enumeration', 'location')], 2)

    def test_success_and_failure_are_cached_until_worker_cleanup(self):
        rows = self.rows(count=6)
        for i, row in enumerate(rows.values()):
            row.update({k: True for k, value in row.items() if isinstance(value, bool)})
            row['workforce'] = i % 2 == 0
        vm = CollectionVM(self.definitions, rows)
        vm.run(NORMAL)
        vm.run(INPUT)
        self.assertEqual(sum(v for (k, _), v in vm.queries.items() if k == 'workforce_evaluation'), 6)
        self.assertEqual(vm.lists['location']['eu5ab_candidate_workforce_checked'], list(rows))
        self.assertEqual(len(vm.lists['location']['eu5ab_candidate_workforce_passed_types']), 3)
        vm.run(INPUT, 'other')
        self.assertEqual(sum(v for (k, _), v in vm.queries.items() if k == 'workforce_evaluation'), 12)
        for row in vm.rows.values():
            row['workforce'] = True
        vm.run(CLEAR)
        vm.run(NORMAL)
        self.assertEqual(len(vm.lists['location']['eu5ab_candidate_workforce_passed_types']), 6)
        vm.run(CLEAR)
        self.assertFalse(any(v for k, v in vm.lists['location'].items() if k.startswith('eu5ab_candidate_')))
        self.assertFalse(any(k.startswith('eu5ab_candidate_') for k in vm.vars['location']))

    def test_food_failures_are_not_lost_and_skip_workforce_evaluation(self):
        rows = self.rows(count=4)
        for (_, row), (gate, _) in zip(rows.items(), FOOD_BUILDING_GATES, strict=True):
            row.update({k: True for k, value in row.items() if isinstance(value, bool)})
            row[gate] = False
        vm = CollectionVM(self.definitions, rows)
        vm.run(NORMAL)
        vm.run(INPUT)
        self.assertEqual(vm.lists['location']['eu5ab_candidate_base_pool'], list(rows))
        self.assertFalse(any(k == 'workforce_evaluation' for k, _ in vm.queries))
        for _, counter in FOOD_BUILDING_GATES:
            self.assertEqual(vm.vars['location']['eu5ab_worker_' + counter], 2)

    def test_capacity_rejection_never_enters_pools_or_queries_workforce(self):
        rows = self.rows(count=3)
        for row in rows.values():
            row.update({key: True for key, value in row.items() if isinstance(value, bool)})
            row['capacity'] = row['kind'] == 'upgrade'
        vm = CollectionVM(self.definitions, rows)
        vm.vars['location']['eu5ab_capacity_ready'] = True
        vm.run(NORMAL)
        vm.run(INPUT)
        for pool, entries in vm.lists['location'].items():
            if pool.startswith('eu5ab_current_'):
                self.assertTrue(all(rows[building]['kind'] == 'upgrade' for building in entries))
        for building, row in rows.items():
            if not row['capacity']:
                self.assertEqual(vm.queries[('workforce_evaluation', building)], 0)
        self.assertEqual(vm.vars['location']['eu5ab_worker_eu5ab_diag_fail_building_capacity'], 4)

    def test_new_classification_is_guarded_by_same_catalog_as_public_predicates(self):
        import re
        triggers = generated_fixture().triggers
        building_sets = []
        for name in ('eu5ab_candidate_is_latest_unlocked', 'eu5ab_candidate_location_can_build',
                     'eu5ab_candidate_has_existing_building', 'eu5ab_candidate_lacks_existing_building'):
            block = _blocks_for_token(triggers, '\n' + name + ' = ')[0]
            # Case labels rather than successor/predecessor references.
            pattern = r'building_type:(\w+) = \{' if 'switch = {' in block else r'this = building_type:(\w+)'
            building_sets.append(set(re.findall(pattern, block)))
            if 'switch = {' in block:
                self.assertIn('fallback = { always = no }', block)
        for entries in building_sets:
            self.assertEqual(entries, building_sets[0])
            self.assertEqual(len(entries), generated_fixture().building_count)

    def test_custom_routes_have_identical_allow_rules(self):
        triggers = {k: v for k, _, v in parse(generated_fixture().triggers)}
        routes = []
        for name in ('eu5ab_current_building_allowed', 'eu5ab_current_input_source_building_allowed'):
            cases = {k: v for k, _, v in triggers[name][0][2]}
            routes.append(cases['100'])
        self.assertEqual(routes[0], routes[1])
