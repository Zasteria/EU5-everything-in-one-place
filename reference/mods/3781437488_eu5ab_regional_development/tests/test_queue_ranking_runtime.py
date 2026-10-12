"""A second project competes using fresh scores and native queued jobs."""
import unittest

from src.eu5autobuild import queue_ranking, queued_workforce, building_capacity
from src.eu5autobuild.generator import render_workforce_script_values
from tests._generated import generated_fixture, _blocks_for_token
from tests._game_data_fixtures import cached_game_data
from tests._governor_script_vm import parse
from tests.test_queue_recovery_runtime import QueueVM
from tests.test_market_supply_runtime import SupplyVM
from tests.test_workforce_runtime import WorkforceValues
from tests.test_engine import RULES


class RankingVM(QueueVM):
    def __init__(self):
        fixture = generated_fixture()
        super().__init__(fixture.effects, fixture.scripted_guis)
        self.definitions.update({k: v for k, _, v in parse(queue_ranking.render(16, 100))})
        self.capacity_values.update({k: v for k, _, v in parse(_blocks_for_token(fixture.values, 'eu5ab_candidate_sort_score = ')[0])})
        self.capacity_values.update({k: v for k, _, v in parse(building_capacity.phase_values(16))})
        self.owners['second'] = self.ROOT
        for name in ('second', 'a', 'b'):
            self.vars[name], self.lists[name] = {}, {}
        self.vars[self.ROOT]['eu5ab_q_phase'] = 16
        self.lists[self.ROOT]['eu5ab_q_phase_16_locations'] = ['location', 'second']
        for name in ('location', 'second'):
            self.lists[name]['eu5ab_q_phase_16_types'] = ['a', 'b']
        self.scores = {('location', 'a'): 100, ('location', 'b'): 90,
                       ('second', 'a'): 70, ('second', 'b'): 80}
        self.invalid = set()

    def test(self, key, op, value, stack):
        if key == 'eu5ab_candidate_route_allowed':
            return ((self.scopes['eu5ab_candidate_location'], stack[-1]) not in self.invalid) == (value == 'yes')
        return super().test(key, op, value, stack)

    def value(self, expression, stack):
        if expression == 'eu5ab_current_candidate_score':
            return self.scores[(self.scopes['eu5ab_candidate_location'], stack[-1])]
        if isinstance(expression, str) and expression.endswith('.eu5ab_current_candidate_score'):
            return self.value('eu5ab_current_candidate_score', stack + [self.target(expression.rsplit('.', 1)[0], stack)])
        return super().value(expression, stack)


class JobsVM(SupplyVM):
    def __init__(self):
        super().__init__()
        self.workforce = cached_game_data()[3]
        self.capacity_values.update({k: v for k, _, v in parse(queued_workforce.render(self.workforce))})

    def value(self, expression, stack):
        if expression == 'building_type.employment_size':
            return self.workforce.all_buildings['iron_foundry'].jobs_per_level / 1000
        if expression == 'eu5ab_rgo_queued_jobs':
            return 0
        if expression == 'eu5ab_rgo_jobs_per_expansion':
            return self.workforce.rgo_jobs_per_level / 1000
        return super().value(expression, stack)

    def test(self, key, op, value, stack):
        if key == 'always':
            return value == 'yes'
        if key == 'building_type' and isinstance(value, str):
            return value == self.target(key, stack)
        return super().test(key, op, value, stack)


class QueueRankingRuntimeTests(unittest.TestCase):
    def test_covered_shortage_cannot_promote_a_worse_project_at_the_same_location(self):
        vm = RankingVM()
        vm.invalid.add(('location', 'a'))
        vm.scores[('location', 'b')] = 10
        vm.run('eu5ab_refresh_planning_queue', vm.ROOT)
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_q_phase_16_locations'], ['second', 'location'])
        self.assertEqual(vm.vars['location']['eu5ab_capacity_phase_16_order'], 10)

    def test_second_wave_reorders_both_locations_and_buildings_and_clears_temporary_state(self):
        vm = RankingVM()
        vm.run('eu5ab_refresh_planning_queue', vm.ROOT)
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_q_phase_16_locations'], ['location', 'second'])
        vm.scores[('location', 'a')] = 10
        vm.scores[('location', 'b')] = 20
        vm.run('eu5ab_refresh_planning_queue', vm.ROOT)
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_q_phase_16_locations'], ['second', 'location'])
        self.assertEqual(vm.lists['location']['eu5ab_q_phase_16_types'], ['b', 'a'])
        self.assertFalse(vm.variable_maps['location'].get('eu5ab_candidate_sort_scores'))
        self.assertFalse(vm.lists[vm.ROOT].get('eu5ab_q_rank_locations'))

    def test_native_queued_levels_reserve_workers_and_cancellation_releases_them(self):
        jobs = JobsVM()
        row = jobs.workforce.buildings['iron_foundry']
        name = 'eu5ab_queued_jobs_' + row.pop_types[0]
        unit = row.jobs_per_level / 1000
        for count in (0, 1, 2, 0):
            jobs.facts['foundry']['building_levels_under_construction'] = count
            self.assertAlmostEqual(jobs.value(name, ['location']), unit * count)

    def test_next_candidate_subtracts_reserved_workers_before_forecast(self):
        recipes, _, upgrades, workforce = cached_game_data()
        definitions = {k: v for k, _, v in parse(render_workforce_script_values(workforce, upgrades, generated_fixture().policies, RULES))}
        vm = WorkforceValues(definitions, 'iron_foundry')
        vm.unemployed = 2
        vm.native['eu5ab_candidate_queued_jobs'] = 1.5
        self.assertAlmostEqual(vm.value('eu5ab_candidate_current_available_workers'), .5)
        vm.native['eu5ab_candidate_queued_jobs'] = 3
        self.assertLessEqual(vm.value('eu5ab_candidate_projected_available_workers'), 0)

    def test_queued_jobs_dispatch_preserves_values_and_stops_at_matching_type(self):
        vm = JobsVM()
        vm.native.pop('eu5ab_candidate_queued_jobs', None)
        name = 'eu5ab_candidate_queued_jobs'
        current = vm.capacity_values[name]
        legacy = [(('if' if k == 'else_if' else k), op, body) for k, op, body in current]
        kinds = sorted(vm.workforce.buildings)
        comparisons = []
        test = vm.test

        def counted(key, op, value, stack):
            if key == 'this' and isinstance(value, str) and value.startswith('building_type:'):
                comparisons.append(value)
            return test(key, op, value, stack)

        vm.test = counted
        for index in (0, len(kinds) // 2, len(kinds) - 1):
            kind = 'building_type:' + kinds[index]
            for queued in (0, 2, 5):
                for pop in vm.workforce.buildings[kinds[index]].pop_types:
                    vm.native['eu5ab_queued_jobs_' + pop] = queued
                expected = vm.value(legacy, [kind])
                comparisons.clear()
                self.assertEqual(vm.value(current, [kind]), expected)
                self.assertEqual(comparisons, ['building_type:' + k for k in kinds[:index + 1]])


if __name__ == '__main__':
    unittest.main()
