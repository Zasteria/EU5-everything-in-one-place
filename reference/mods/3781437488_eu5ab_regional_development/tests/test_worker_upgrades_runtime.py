"""Execute predecessor snapshots against the retained live predicates/formula."""

import unittest
from itertools import product

from src.eu5autobuild.generator import FOOD_BUILDING_GATES, _catalog_building_ids
from src.eu5autobuild.worker_screening import ACTIVE, mapping
from src.eu5autobuild.worker_upgrades import LOCATION_PASSED, PREDICATES
from tests._game_data_fixtures import cached_game_data
from tests._generated import generated_fixture, _blocks_for_token
from tests._governor_script_vm import parse
from tests.test_worker_screening_runtime import WorkerVM
from tests.test_candidate_collection_runtime import NORMAL


class UpgradeVM(WorkerVM):
    def __init__(self, definitions, destination, instances):
        target = 'building_type:' + destination
        row = dict.fromkeys(('allowed', 'special', 'latest', 'legal', 'workforce',
                             *(gate for gate, _ in FOOD_BUILDING_GATES)), True)
        super().__init__(definitions, {target: row}, memo=True)
        self.scopes.update(eu5ab_candidate_location='location', eu5ab_candidate_building=target)
        self.instances = {f'instance_{i}': row for i, row in enumerate(instances)}
        self.vars['location']['eu5ab_capacity_open'] = True
        self.unemployed = 1000

    def value(self, word, stack):
        if isinstance(word, str):
            if word.startswith('location_unemployed_population_for_building_type('):
                return self.unemployed
            if word.startswith('eu5ab_scan_queued_jobs_') or word.endswith('eu5ab_candidate_projected_promotion'):
                return 0
            if word in self.definitions and 'jobs' in word:
                return super().value(self.definitions[word], stack)
            if word.startswith('building_type:'):
                return word
        return super().value(word, stack)

    def test(self, k, op, v, stack):
        if k == 'can_build_building':
            self.queries[('location_permission', v)] += 1
            return self.rows[v]['legal']
        if k in ('eu5ab_candidate_location_eligible', 'eu5ab_candidate_has_capacity',
                 'eu5ab_candidate_capacity_exempt'):
            return self.condition(self.definitions[k], stack) == (v == 'yes')
        if k == 'employment_size':
            jobs = self.rows[stack[-1]].get('employment', 1)
            return jobs > float(v) if op == '>' else jobs <= float(v)
        if k == 'eu5ab_candidate_is_upgrade':
            return self.test('eu5ab_candidate_replaces_existing_building', '=', v, stack)
        if k == 'eu5ab_candidate_has_existing_building':
            return any('building_type:' + row['type'] == stack[-1] and row['level'] >= 1
                       for row in self.instances.values()) == (v == 'yes')
        if k == 'switch':
            fields = {a: c for a, _, c in v}
            return self.condition(fields.get(self.value(fields['trigger'], stack),
                                             fields.get('fallback', [('always', '=', 'no')])), stack)
        if k in (*PREDICATES.values(), *(name + '_worker_live' for name in PREDICATES.values())):
            return self.condition(self.definitions[k], stack) == (v == 'yes')
        if k == 'any_buildings_in_location':
            return any(self.condition(v, stack + [instance]) for instance in self.instances)
        if k == 'building_type':
            row = self.instances[stack[-1]]
            if isinstance(v, list):
                self.assert_employment_gate(v)
                return row['employment'] > 0
            return v == 'building_type:' + row['type']
        if k == 'building_level':
            assert op == '>='
            return self.instances[stack[-1]]['level'] >= float(v)
        if k == 'building_can_be_upgraded_by':
            self.queries[('upgrade_permission', stack[-1])] += 1
            return self.instances[stack[-1]]['allowed']
        if k == 'eu5ab_upgrade_source_available':
            row = self.instances[stack[-1]]
            return (row['level'] > row.get('reserved', 0)) == (v == 'yes')
        return super().test(k, op, v, stack)

    @staticmethod
    def assert_employment_gate(entries):
        assert entries == [('employment_size', '>', '0')], entries

    def execute(self, entries, stack):
        index = 0
        while index < len(entries):
            k, _, body = entries[index]
            end = index + 1
            if k == 'if':
                while end < len(entries) and entries[end][0] in ('else_if', 'else'):
                    end += 1
            if k == 'every_buildings_in_location':
                self.queries[('predecessor_scan', self.scopes['eu5ab_candidate_building'])] += 1
                gate = next(v for k, _, v in body if k == 'limit')
                for instance in self.instances:
                    if self.condition(gate, stack + [instance]):
                        self.execute([e for e in body if e[0] != 'limit'], stack + [instance])
            elif k in ('eu5ab_prepare_worker_location_eligibility', 'eu5ab_evaluate_candidate_workforce'):
                self.execute(self.definitions[k], stack)
            elif k.startswith(('eu5ab_prepare_promotion_', 'eu5ab_prepare_scan_queued_jobs_')):
                pass  # Inject zero promotion/reservations; workforce tests cover their arithmetic.
            else:
                super().execute(entries[index:end], stack)
            index = end

    def facts(self):
        stack = [self.scopes['eu5ab_candidate_building']]
        return (*(self.test(name, '=', 'yes', stack) for name in PREDICATES.values()),
                self.value('eu5ab_candidate_net_new_jobs', stack))


class WorkerUpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        f = generated_fixture()
        cls.definitions = {}
        for source, names in (
            (f.effects, ('eu5ab_prepare_worker_screen_upgrades', 'eu5ab_clear_worker_screening',
                         'eu5ab_prepare_worker_location_eligibility', NORMAL,
                         'eu5ab_prepare_candidate_collection_gate', 'eu5ab_prepare_candidate_workforce',
                         'eu5ab_evaluate_candidate_workforce')),
            (f.triggers, (*PREDICATES.values(), *(n + '_worker_live' for n in PREDICATES.values()),
                          'eu5ab_candidate_location_eligible', 'eu5ab_candidate_has_capacity',
                          'eu5ab_candidate_capacity_exempt')),
            (f.values, ('eu5ab_candidate_net_new_jobs', 'eu5ab_candidate_net_new_jobs_worker_live',
                        'eu5ab_candidate_jobs_per_level')),
        ):
            cls.definitions.update({n: parse(_blocks_for_token(source, '\n' + n + ' = ')[0])[0][2] for n in names})

    def test_distinct_facts_match_live_rules_and_permission_is_read_once(self):
        _, _, upgrades, workforce = cached_game_data()
        for destination, predecessors in upgrades.predecessors.items():
            if not predecessors or destination not in workforce.buildings:
                continue
            for level, employment, allowed in ((1, 1, True), (0, 1, True),
                                                (1, 0, True), (1, 1, False)):
                with self.subTest(destination=destination, level=level, employment=employment, allowed=allowed):
                    rows = [dict(type=p, level=level, employment=employment, allowed=allowed) for p in predecessors]
                    vm = UpgradeVM(self.definitions, destination, rows)
                    expected = vm.facts()  # No ready entry: execute retained live rules.
                    vm.queries.clear()
                    target = vm.scopes['eu5ab_candidate_building']
                    vm.execute(self.definitions['eu5ab_prepare_worker_screen_upgrades'], [target])
                    self.assertEqual(vm.facts()[:2], expected[:2])
                    self.assertAlmostEqual(vm.facts()[2], expected[2])
                    before = vm.queries.copy()
                    vm.execute(self.definitions['eu5ab_prepare_worker_screen_upgrades'], [target])
                    self.assertEqual(vm.facts()[:2], expected[:2])
                    self.assertAlmostEqual(vm.facts()[2], expected[2])
                    self.assertEqual(vm.queries, before)
                    self.assertTrue(all(count == 1 for (kind, _), count in before.items() if kind == 'upgrade_permission'))
                    if expected[2] == 0:
                        self.assertNotIn(target, vm.maps['location'][mapping('net_new_jobs')])
                    vm.execute(self.definitions['eu5ab_clear_worker_screening'], ['location'])
                    self.assertNotIn(ACTIVE, vm.vars['location'])
                    self.assertFalse(any(vm.maps['location'].values()))
                    for row in vm.instances.values():
                        row['allowed'] = False
                    self.assertEqual(vm.facts(), (False, False, workforce.buildings[destination].jobs_per_level / 1000))

    def test_lazy_legality_matches_live_for_catalog_and_unknown(self):
        upgrades = cached_game_data()[2]
        for building in [*_catalog_building_ids(generated_fixture().catalog), 'unknown']:
            for legal, allowed in product((False, True), repeat=2):
                with self.subTest(building=building, legal=legal, allowed=allowed):
                    rows = [dict(type=p, level=1, employment=1, allowed=allowed)
                            for p in upgrades.predecessors.get(building, ())]
                    vm = UpgradeVM(self.definitions, building, rows)
                    target = vm.scopes['eu5ab_candidate_building']
                    vm.rows[target]['legal'] = legal
                    expected = vm.test('eu5ab_candidate_location_eligible', '=', 'yes', [target])
                    vm.queries.clear()
                    vm.vars['location'][LOCATION_PASSED] = True
                    vm.execute(self.definitions['eu5ab_prepare_worker_location_eligibility'], [target])
                    self.assertEqual(LOCATION_PASSED in vm.vars['location'], expected)
                    self.assertEqual(vm.queries[('location_permission', target)], int(building != 'unknown'))
                    if legal or not rows:
                        self.assertFalse(any(vm.maps['location'].values()))
                    elif rows:
                        self.assertEqual(vm.queries[('predecessor_scan', target)], 1)
                    vm.execute(self.definitions['eu5ab_clear_worker_screening'], ['location'])
                    self.assertNotIn(LOCATION_PASSED, vm.vars['location'])

    def test_collection_prepares_only_when_needed_and_still_classifies_upgrades(self):
        building = 'iron_foundry'
        predecessors = cached_game_data()[2].predecessors[building]
        for legal, open_capacity, food, pause in (
            (True, True, False, True),   # Rejected before any predecessor fact is needed.
            (False, True, False, True),  # Legality needs the replacement exception.
            (True, False, False, True),  # Capacity needs the replacement exception.
            (True, True, True, True),   # Different professions: classify after workforce.
            (True, True, True, False),  # Protection disabled: classification is first use.
        ):
            with self.subTest(legal=legal, capacity=open_capacity, food=food, pause=pause):
                rows = [dict(type=p, level=1, employment=1, allowed=True) for p in predecessors]
                vm = UpgradeVM(self.definitions, building, rows)
                target = vm.scopes['eu5ab_candidate_building']
                vm.rows[target].update(legal=legal, **{FOOD_BUILDING_GATES[0][0]: food})
                vm.vars[vm.ROOT]['eu5ab_global_pause_low_workforce'] = int(pause)
                if not open_capacity:
                    vm.vars['location'].pop('eu5ab_capacity_open')
                vm.run(NORMAL)
                expected_scans = int(not legal or not open_capacity or food)
                self.assertEqual(vm.queries[('predecessor_scan', target)], expected_scans)
                self.assertTrue(all(n == 1 for (kind, _), n in vm.queries.items() if kind == 'upgrade_permission'))
                self.assertEqual(vm.lists['location']['eu5ab_current_upgrade_candidate_pool'], [target] if food else [])
                self.assertFalse(vm.lists['location']['eu5ab_current_new_candidate_pool'])
                self.assertFalse(vm.lists['location']['eu5ab_current_expansion_candidate_pool'])
                self.assertNotIn(LOCATION_PASSED, vm.vars['location'])
                if not expected_scans:
                    self.assertFalse(any(vm.maps['location'].get(mapping(k)) for k in ('net_new_jobs_ready', 'replaces_existing')))

    def test_workforce_first_use_reads_once_then_classification_reuses(self):
        building = 'beer_workshop'
        predecessors = cached_game_data()[2].predecessors[building]
        rows = [dict(type=p, level=1, employment=1, allowed=True) for p in predecessors]
        vm = UpgradeVM(self.definitions, building, rows)
        target = vm.scopes['eu5ab_candidate_building']
        expected_jobs = vm.facts()[2]
        vm.queries.clear()
        vm.unemployed = expected_jobs
        vm.execute(self.definitions['eu5ab_prepare_candidate_workforce'], [target])
        self.assertIn('eu5ab_candidate_workforce_passed', vm.vars['location'])
        self.assertEqual(vm.queries[('predecessor_scan', target)], 1)
        before = vm.queries.copy()
        vm.execute(self.definitions['eu5ab_prepare_worker_screen_upgrades'], [target])
        self.assertTrue(vm.test('eu5ab_candidate_is_upgrade', '=', 'yes', [target]))
        self.assertAlmostEqual(vm.facts()[2], expected_jobs)
        self.assertEqual(vm.queries, before)

    def test_reserved_predecessor_has_no_second_capacity_or_workforce_credit(self):
        building = 'beer_workshop'
        predecessor = cached_game_data()[2].predecessors[building][0]
        for level, reserved in ((3, 1), (1, 1), (0, 0)):
            vm = UpgradeVM(self.definitions, building,
                           [dict(type=predecessor, level=level, reserved=reserved, employment=1, allowed=True)])
            target = vm.scopes['eu5ab_candidate_building']
            full = cached_game_data()[3].buildings[building].jobs_per_level / 1000
            expected = vm.facts()
            vm.execute(self.definitions['eu5ab_prepare_worker_screen_upgrades'], [target])
            self.assertEqual(vm.facts(), expected)
            self.assertEqual(vm.facts()[:2], (level > reserved, level > reserved))
            if level == reserved:
                self.assertEqual(vm.facts()[2], full)


if __name__ == '__main__':
    unittest.main()
