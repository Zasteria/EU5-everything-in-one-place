"""Execute generated workforce arithmetic with injected vanilla query results."""
import unittest
from collections import Counter
from dataclasses import replace

from src.eu5autobuild import queued_workforce
from src.eu5autobuild.generator import (
    POLICY_FILE, RULES_FILE, render_workforce_cache_effects,
    render_workforce_script_values,
)
from src.eu5autobuild.policy import load_policies
from src.eu5autobuild.rules import load_automation_rules
from tests._game_data_fixtures import cached_game_data
from tests._governor_script_vm import parse


class WorkforceValues:
    def __init__(self, definitions, building):
        self.definitions = definitions
        self.building = building
        self.cache = {}
        self.speed = 0.02
        self.months = 12
        self.sources = 0.07
        self.unemployed = 0.04
        self.upgradable = set()
        self.population_queries = 0
        self.pause_low_workforce = True
        self.queued_jobs = {}
        self.queued_queries = Counter()
        self.queued_type_lookups = 0
        # Native queued-job readings are injected by the queue-specific tests.
        self.native = {'eu5ab_candidate_queued_jobs': 0,
                       'scope:eu5ab_candidate_building.eu5ab_candidate_queued_jobs': 0}

    def condition(self, entries):
        for key, _, value in entries:
            if key == 'this':
                result = value == 'building_type:' + self.building
            elif key == 'NOT':
                result = not self.condition(value)
            elif key == 'has_variable':
                result = value in self.cache
            elif key == 'scope:eu5ab_candidate_location':
                result = self.condition(value)
            elif key == 'scope:eu5ab_candidate_location.owner.var:eu5ab_global_pause_low_workforce':
                result = self.pause_low_workforce
            elif key == 'any_buildings_in_location':
                predecessor = next(v for k, _, v in value if k == 'building_type')
                result = predecessor.removeprefix('building_type:') in self.upgradable
            else:
                raise AssertionError(key)
            if not result:
                return False
        return True

    def value(self, expression):
        if isinstance(expression, list):
            return self.execute(expression)
        if expression == 'eu5ab_candidate_queued_jobs':
            self.queued_type_lookups += 1
        if expression.startswith('eu5ab_queued_jobs_'):
            pop = expression.removeprefix('eu5ab_queued_jobs_')
            self.queued_queries[pop] += 1
            return self.queued_jobs.get(pop, 0)
        if expression in self.native:
            return self.native[expression]
        if expression in self.definitions:
            return self.execute(self.definitions[expression])
        if '.var:eu5ab_scan_promotion_' in expression:
            return self.cache[expression.split('.var:')[1]]
        if expression.endswith('.eu5ab_location_combined_pop_promotion_speed'):
            return self.speed
        if expression.endswith('.var:eu5ab_global_job_fill_deadline_months'):
            return self.months
        if '.location_unemployed_population_for_building_type(' in expression:
            return self.unemployed
        if '.unemployed_pops_of_pop_type_in_location(' in expression:
            self.population_queries += 1
            return self.sources
        return float(expression)

    def execute(self, entries, result=0):
        matched = False
        for key, _, value in entries:
            if key in ('if', 'else_if', 'else'):
                if key == 'if':
                    matched = False
                allowed = key == 'else' or self.condition(value[0][2])
                if not matched and allowed:
                    result = self.execute(value if key == 'else' else value[1:], result)
                    matched = True
            elif key == 'value':
                result = self.value(value)
            elif key == 'add':
                result += self.value(value)
            elif key == 'subtract':
                result -= self.value(value)
            elif key == 'multiply':
                result *= self.value(value)
            elif key == 'max':
                result = min(result, self.value(value))
            elif key == 'min':
                result = max(result, self.value(value))
            elif key == 'owner':
                result = self.execute(value, result)
            else:
                raise AssertionError(key)
        return result


class WorkforceEffectVM(WorkforceValues):
    """Execute the merged dispatch with the same injected native values."""
    def condition(self, entries):
        for key, op, value in entries:
            if key.startswith('var:'):
                if op != '>=':
                    raise AssertionError(op)
                if self.value(key) < self.value(value):
                    return False
            elif key == 'eu5ab_candidate_projected_workforce_sufficient':
                result = self.value('eu5ab_candidate_projected_available_workers') >= self.value('eu5ab_candidate_net_new_jobs')
                if result != (value == 'yes'):
                    return False
            elif not super().condition([(key, op, value)]):
                return False
        return True

    def value(self, expression):
        if isinstance(expression, str):
            if expression.startswith('var:'):
                return self.cache.get(expression[4:], 0)
            if expression.startswith('location_unemployed_population_for_building_type('):
                if expression != f'location_unemployed_population_for_building_type(building_type:{self.building})':
                    raise AssertionError(expression)
                self.native_queries += 1
                return self.unemployed
            if expression.startswith('scope:eu5ab_candidate_building.'):
                return super().value(expression.split('.', 1)[1])
        return super().value(expression)

    def run_effect(self, entries, definitions=None):
        if definitions is not None:
            self.effects = definitions
        matched = False
        for key, _, value in entries:
            if key == 'switch':
                cases = {k: v for k, _, v in value}
                self.run_effect(cases.get('building_type:' + self.building, cases.get('fallback', [])))
            elif key == 'scope:eu5ab_candidate_location':
                self.run_effect(value)
            elif key == 'set_variable':
                if isinstance(value, list):
                    assignment = {k: v for k, _, v in value}
                    result = self.value(assignment['value'])
                    if result == 0:
                        self.cache.pop(assignment['name'], None)
                    else:
                        self.cache[assignment['name']] = result
                else:
                    self.cache[value] = True
            elif key == 'remove_variable':
                self.cache.pop(value, None)
            elif key in ('if', 'else_if', 'else'):
                if key == 'if':
                    matched = False
                if not matched and (key == 'else' or self.condition(value[0][2])):
                    self.run_effect(value if key == 'else' else value[1:])
                    matched = True
            elif key in self.effects:
                self.run_effect(self.effects[key])
            else:
                raise AssertionError(key)


class WorkforceRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, _, cls.upgrades, cls.workforce = cached_game_data()
        cls.definitions = dict((k, v) for k, _, v in parse(render_workforce_script_values(
            cls.workforce, cls.upgrades, load_policies(POLICY_FILE),
            load_automation_rules(RULES_FILE),
        )))
        cls.definitions.update({k: v for k, _, v in parse(queued_workforce.render(cls.workforce))})
        cls.effects = dict((k, v) for k, _, v in parse(
            render_workforce_cache_effects(cls.workforce, cls.upgrades)
        ))

    def test_all_buildings_preserve_jobs_upgrade_order_and_uncached_forecast(self):
        # These cases execute the emitted branches against the metadata model,
        # including unknown buildings, zero horizon and source-limited promotion.
        for building, row in self.workforce.buildings.items():
            vm = WorkforceValues(self.definitions, building)
            with self.subTest(building=building):
                self.assertAlmostEqual(vm.value('eu5ab_candidate_jobs_per_level'), row.jobs_per_level / 1000)
                self.assertEqual(vm.value('eu5ab_candidate_current_available_workers'), vm.unemployed)
                predecessors = sorted(
                    (p for p in self.upgrades.predecessors.get(building, ()) if p in self.workforce.all_buildings
                     and self.workforce.all_buildings[p].pop_types == row.pop_types),
                    key=lambda p: (-self.workforce.all_buildings[p].jobs_per_level, p),
                )
                for eligible in [set(), *({p} for p in predecessors), set(predecessors)]:
                    vm.upgradable = eligible
                    reduction = next((self.workforce.all_buildings[p].jobs_per_level for p in predecessors if p in eligible), 0)
                    self.assertAlmostEqual(vm.value('eu5ab_candidate_net_new_jobs'), (row.jobs_per_level - min(row.jobs_per_level, reduction)) / 1000)
                target = row.pop_types[0]
                path = self.workforce.promotion_paths.get(target)
                factor = path.promotion_factor if path else 1
                source_count = sum(target in p.targets for p in self.workforce.promotion_paths.values())
                for months in (0, 12, 96, 240):
                    vm.months = months
                    expected = min(vm.speed * factor * months, source_count * vm.sources)
                    self.assertAlmostEqual(vm.value('eu5ab_candidate_projected_promotion'), expected)
        vm = WorkforceValues(self.definitions, 'unknown_building')
        for name in ('jobs_per_level', 'net_new_jobs', 'current_available_workers', 'projected_promotion'):
            self.assertEqual(vm.value('eu5ab_candidate_' + name), 0)

    def test_cache_uses_same_target_only_and_clear_forces_fresh_formula(self):
        cases = dict((k, v) for k, _, v in self.effects['eu5ab_cache_candidate_promotion'][0][2][1][2] if k != 'trigger')
        cache = {}
        expected_by_target = {}
        for building, row in self.workforce.buildings.items():
            vm = WorkforceValues(self.definitions, building)
            vm.cache = cache
            # Execute the actual selected case's guard and assignment RHS.
            location = cases['building_type:' + building][0][2]
            guarded = location[0][2]
            if vm.condition(guarded[0][2]):
                assignment = dict((k, v) for k, _, v in guarded[1][2])
                rhs = assignment['value'].removeprefix('scope:eu5ab_candidate_building.')
                cache[assignment['name']] = vm.value(rhs)
            value = vm.value('eu5ab_candidate_projected_promotion')
            target = row.pop_types[0]
            if target in expected_by_target:
                self.assertEqual(vm.population_queries, 0)
                self.assertEqual(value, expected_by_target[target])
            expected_by_target[target] = value
        for key, _, variable in self.effects['eu5ab_clear_scan_promotion_cache']:
            self.assertEqual(key, 'remove_variable')
            cache.pop(variable, None)
        self.assertEqual(cache, {})
        vm.months = 0
        self.assertEqual(vm.value('eu5ab_candidate_projected_promotion'), 0)

    def test_disabled_switch_never_reads_promotion_sources_or_cached_forecast(self):
        for building, row in self.workforce.buildings.items():
            vm = WorkforceValues(self.definitions, building)
            vm.pause_low_workforce = False
            vm.cache['eu5ab_scan_promotion_' + row.pop_types[0]] = 123
            self.assertEqual(vm.value('eu5ab_candidate_projected_promotion'), 0)
            self.assertEqual(vm.population_queries, 0)

    def test_promotion_aggregates_opportunities_and_literacy_once(self):
        vm = WorkforceValues(self.definitions, 'unknown_building')
        vm.native.update({
            'modifier:local_pop_promotion_speed': .001,
            'modifier:global_pop_promotion_speed': 0,
            'modifier:local_pop_promotion_speed_scaled': .001,
            'population': 9,
            'modifier:local_pop_promotion_speed_modifier': .7384,
            'modifier:global_pop_promotion_speed_modifier': 0,
        })
        # Injected example: 1 base person + 9 from population scaling,
        # then +73.84% speed. The result is still in thousands per month.
        self.assertAlmostEqual(vm.value('eu5ab_location_combined_pop_promotion_speed'), .017384)

    def assert_merged_matches(self, building, row, *, effects=None):
        effects = self.effects if effects is None else effects
        vm = WorkforceEffectVM(self.definitions, building)
        predecessors = self.upgrades.predecessors.get(building, ())
        for eligible in [set(), *({p} for p in predecessors), set(predecessors)]:
            vm.upgradable = eligible
            for cached in (False, True):
                for months in (0, 12, 96, 240):
                    vm.cache = {}
                    vm.months = months
                    if cached and row:
                        vm.cache['eu5ab_scan_promotion_' + row.pop_types[0]] = vm.value('eu5ab_candidate_projected_promotion')
                    required = vm.value('eu5ab_candidate_net_new_jobs')
                    promotion = vm.value('eu5ab_candidate_projected_promotion')
                    # Include exact equality, adjacent thousandth boundaries,
                    # zero-job replacements and insufficient/abundant labor.
                    boundary = required - promotion
                    for unemployed in (0, .04, 10, boundary - .001, boundary, boundary + .001):
                        vm.unemployed = unemployed
                        expected = vm.value('eu5ab_candidate_projected_available_workers') >= required
                        vm.cache.pop('eu5ab_candidate_workforce_passed', None)
                        vm.native_queries = 0
                        vm.run_effect(effects['eu5ab_evaluate_candidate_workforce'], effects)
                        with self.subTest(building=building, eligible=eligible, cached=cached, months=months, unemployed=unemployed):
                            self.assertEqual('eu5ab_candidate_workforce_passed' in vm.cache, expected)
                            self.assertNotIn('eu5ab_candidate_required_workers', vm.cache)
                            self.assertNotIn('eu5ab_candidate_available_workers', vm.cache)
                            self.assertEqual(vm.native_queries, 1 if row else 0)

    def test_merged_dispatch_matches_original_gate_for_all_buildings(self):
        for building, row in self.workforce.buildings.items():
            self.assert_merged_matches(building, row)
        self.assert_merged_matches('unknown_building', None)

    def test_lazy_promotion_is_prepared_once_per_target_and_uncached_calls_stay_live(self):
        cache = {'eu5ab_scan_promotion_active': True}
        seen = set()
        for building, row in self.workforce.buildings.items():
            vm = WorkforceEffectVM(self.definitions, building)
            vm.cache = cache
            vm.native_queries = 0
            vm.run_effect(self.effects['eu5ab_evaluate_candidate_workforce'], self.effects)
            target = row.pop_types[0]
            self.assertIn('eu5ab_scan_promotion_' + target + '_ready', cache)
            if target in seen:
                self.assertEqual(vm.population_queries, 0)
            seen.add(target)
        for _, _, variable in self.effects['eu5ab_clear_scan_promotion_cache']:
            cache.pop(variable, None)
        vm.population_queries = 0
        vm.run_effect(self.effects['eu5ab_evaluate_candidate_workforce'], self.effects)
        self.assertGreater(vm.population_queries, 0)
        self.assertNotIn('eu5ab_scan_promotion_' + target, cache)

    def test_zero_promotion_remains_cached_when_numeric_zero_is_removed(self):
        for entrypoint in ('eu5ab_cache_candidate_promotion', 'eu5ab_evaluate_candidate_workforce'):
            cache = {'eu5ab_scan_promotion_active': True}
            targets = set()
            for building, row in self.workforce.buildings.items():
                vm = WorkforceEffectVM(self.definitions, building)
                vm.cache, vm.sources = cache, 0
                vm.native_queries = 0
                target = row.pop_types[0]
                vm.run_effect(self.effects[entrypoint], self.effects)
                if target in targets:
                    self.assertEqual(vm.population_queries, 0)
                calls = vm.population_queries
                self.assertEqual(vm.value('eu5ab_candidate_projected_promotion'), 0)
                self.assertEqual(vm.population_queries, calls)
                self.assertNotIn('eu5ab_scan_promotion_' + target, cache)
                self.assertIn('eu5ab_scan_promotion_' + target + '_ready', cache)
                targets.add(target)

    def test_merged_dispatch_handles_predecessor_outside_supported_catalog(self):
        building = next(iter(self.workforce.buildings))
        row = self.workforce.buildings[building]
        workforce = replace(self.workforce, all_buildings={**self.workforce.all_buildings,
            'unsupported_predecessor': replace(row, building_id='unsupported_predecessor', jobs_per_level=row.jobs_per_level + 1000)})
        upgrades = replace(self.upgrades, predecessors={**self.upgrades.predecessors,
            building: ('unsupported_predecessor',)})
        effects = {k: v for k, _, v in parse(render_workforce_cache_effects(workforce, upgrades))}
        vm = WorkforceEffectVM(self.definitions, building)
        vm.upgradable = {'unsupported_predecessor'}
        vm.unemployed, vm.months, vm.native_queries = 0, 0, 0
        vm.run_effect(effects['eu5ab_evaluate_candidate_workforce'], effects)
        self.assertIn('eu5ab_candidate_workforce_passed', vm.cache)

    def test_scan_queued_jobs_are_shared_per_population_including_zero(self):
        pops = queued_workforce.scan_pop_types(self.workforce)
        for amount in (0, 2.375):
            with self.subTest(amount=amount):
                cache = {'eu5ab_scan_promotion_active': True}
                queries = Counter()
                for building in self.workforce.buildings:
                    vm = WorkforceEffectVM(self.definitions, building)
                    vm.cache, vm.queued_queries = cache, queries
                    vm.queued_jobs = dict.fromkeys(pops, amount)
                    vm.native_queries = 0
                    vm.run_effect(self.effects['eu5ab_evaluate_candidate_workforce'], self.effects)
                    self.assertEqual(vm.queued_type_lookups, 0)
                self.assertEqual(queries, Counter(dict.fromkeys(pops, 1)))
                for pop in pops:
                    self.assertIn('eu5ab_scan_queued_jobs_' + pop + '_ready', cache)
                    self.assertEqual('eu5ab_scan_queued_jobs_' + pop in cache, amount != 0)
                vm.run_effect(self.effects['eu5ab_clear_scan_promotion_cache'], self.effects)
                self.assertFalse(any(key.startswith('eu5ab_scan_queued_jobs_') for key in cache))
                self.assertNotIn('eu5ab_scan_promotion_active', cache)
                # The next location evaluation must observe changed queues.
                cache['eu5ab_scan_promotion_active'] = True
                vm.queued_jobs = dict.fromkeys(pops, amount + 1)
                before = queries.copy()
                vm.run_effect(self.effects['eu5ab_evaluate_candidate_workforce'], self.effects)
                for pop in self.workforce.buildings[vm.building].pop_types:
                    self.assertEqual(queries[pop], before[pop] + 1)
                    self.assertEqual(cache['eu5ab_scan_queued_jobs_' + pop], amount + 1)

    def test_known_building_direct_reservation_preserves_nonzero_queue_boundaries(self):
        amounts = {pop: (index + 1) / 8 for index, pop in enumerate(queued_workforce.scan_pop_types(self.workforce))}
        for building, row in self.workforce.buildings.items():
            vm = WorkforceEffectVM(self.definitions, building)
            vm.queued_jobs = amounts
            vm.cache['eu5ab_scan_promotion_active'] = True
            vm.months, vm.native_queries = 0, 0
            reserved = max([0] + [amounts[pop] for pop in row.pop_types])
            vm.native['eu5ab_candidate_queued_jobs'] = reserved
            for predecessors in (set(), set(self.upgrades.predecessors.get(building, ()))):
                vm.upgradable = predecessors
                required = vm.value('eu5ab_candidate_net_new_jobs')
                for delta in (-.001, 0, .001):
                    vm.unemployed = required + reserved + delta
                    expected = vm.value('eu5ab_candidate_projected_available_workers') >= required
                    vm.cache.pop('eu5ab_candidate_workforce_passed', None)
                    lookups = vm.queued_type_lookups
                    vm.run_effect(self.effects['eu5ab_evaluate_candidate_workforce'], self.effects)
                    with self.subTest(building=building, predecessors=predecessors, delta=delta):
                        self.assertEqual('eu5ab_candidate_workforce_passed' in vm.cache, expected)
                        self.assertEqual(vm.queued_type_lookups, lookups)

    def test_multi_population_uses_max_and_caches_are_location_local(self):
        building = 'iron_foundry'
        row = replace(self.workforce.buildings[building], pop_types=('laborers', 'peasants'))
        workforce = replace(self.workforce, buildings={**self.workforce.buildings, building: row})
        effects = {k: v for k, _, v in parse(render_workforce_cache_effects(workforce, self.upgrades))}
        places = []
        for reservations, expected in (({'laborers': 2, 'peasants': 5}, True),
                                       ({'laborers': 9, 'peasants': 1}, False)):
            vm = WorkforceEffectVM(self.definitions, building)
            vm.cache['eu5ab_scan_promotion_active'] = True
            vm.queued_jobs, vm.months, vm.native_queries = reservations, 0, 0
            vm.unemployed = row.jobs_per_level / 1000 + 5
            vm.run_effect(effects['eu5ab_evaluate_candidate_workforce'], effects)
            self.assertEqual('eu5ab_candidate_workforce_passed' in vm.cache, expected)
            self.assertEqual(vm.queued_queries, Counter(laborers=1, peasants=1))
            places.append(vm)
        self.assertEqual(places[0].cache['eu5ab_scan_queued_jobs_laborers'], 2)
        self.assertEqual(places[1].cache['eu5ab_scan_queued_jobs_laborers'], 9)

    def test_inactive_scan_readers_ignore_stale_values_and_follow_live_queue_changes(self):
        vm = WorkforceEffectVM(self.definitions, 'iron_foundry')
        for pop in queued_workforce.scan_pop_types(self.workforce):
            name = 'eu5ab_scan_queued_jobs_' + pop
            vm.cache.update({name: 99, name + '_ready': True})
            for amount in (2, 0, 7):
                vm.queued_jobs[pop] = amount
                vm.run_effect(self.effects['eu5ab_prepare_scan_queued_jobs_' + pop], self.effects)
                self.assertEqual(vm.value(name), amount)
            self.assertEqual(vm.queued_queries[pop], 3)
            self.assertEqual(vm.cache[name], 99)  # A live read never publishes a cache.
