"""Combined collection dispatch must preserve native predicates and their order."""
from itertools import product
import unittest

from tests._generated import generated_fixture, _blocks_for_token
from tests._game_data_fixtures import cached_game_data
from tests._governor_script_vm import parse
from tests.test_candidate_score_optimizations import ScoreVM


class EligibilityVM(ScoreVM):
    def predicate(self, key, op, value):
        if key == 'switch':
            self.switches += 1
            fields = {k: v for k, _, v in value}
            return self.condition(fields.get('building_type:' + self.building,
                                             fields.get('fallback', [('always', '=', 'no')])))
        if key == 'any_buildings_in_location':
            for row in self.existing:
                self.existing_building = row
                if self.condition(value):
                    return True
            return False
        if key == 'building_type':
            if isinstance(value, list):
                return self.condition(value)
            return value == 'building_type:' + self.existing_building[0]
        if key == 'building_level':
            return self.existing_building[1] >= int(value)
        if key == 'employment_size':
            return self.existing_building[2] > int(value)
        if key == 'building_can_be_upgraded_by':
            self.calls.append(('upgrade_permission', self.existing_building[0]))
            return self.existing_building[3]
        if key == 'scope:eu5ab_candidate_location.owner':
            self.owner_scope = True
            try:
                return self.condition(value)
            finally:
                self.owner_scope = False
        if key == 'NOR':
            return not any(self.predicate(*item) for item in value)
        if key == 'can_build_building':
            if not getattr(self, 'owner_scope', False):
                self.calls.append(('legal', value.removeprefix('building_type:')))
                return self.legal
            self.calls.append(('unlocked', value))
            return value.removeprefix('building_type:') in self.unlocked
        if key == 'location_and_owner_can_build':
            building = dict((k, v) for k, _, v in value)['building_type']
            self.calls.append(('legal', building))
            if self.legal:
                # Installed vanilla macro checks the owner again after the
                # location. The combined gate has already proved this fact.
                self.calls.append(('unlocked', 'building_type:' + building))
                return building in self.unlocked
            return False
        return super().predicate(key, op, value)


class CandidateBaseEligibilityTests(unittest.TestCase):
    def test_all_catalog_buildings_and_unknown_preserve_checks_and_short_circuit(self):
        fixture = generated_fixture()
        names = ('eu5ab_candidate_is_latest_unlocked', 'eu5ab_candidate_location_can_build',
                 'eu5ab_candidate_base_eligible', 'eu5ab_candidate_replaces_existing_building')
        triggers = {name: parse(_blocks_for_token(fixture.triggers, '\n' + name + ' = ')[0])[0][2]
                    for name in (*names, 'eu5ab_candidate_replaces_existing_building_worker_live')}
        upgrades = cached_game_data()[2]
        vm = EligibilityVM({}, triggers)
        for building in [*fixture.catalog.buildings, 'unknown']:
            vm.building = building
            for unlocked, successors, legal, replacement in product((False, True), repeat=4):
                vm.unlocked = ({building} if unlocked else set()) | (set(upgrades.successors.get(building, ())) if successors else set())
                vm.legal = legal
                vm.existing = [('unrelated', 1, 100, True)] + [
                    (p, 1, 100, replacement) for p in upgrades.predecessors.get(building, ())]
                vm.switches = 0
                vm.calls = []
                expected = vm.condition(triggers[names[0]]) and vm.condition(triggers[names[1]])
                before = vm.calls.copy()
                vm.calls = []
                vm.switches = 0
                actual = vm.condition(triggers[names[2]])
                with self.subTest(building=building, unlocked=unlocked, successors=successors, legal=legal, replacement=replacement):
                    self.assertEqual(actual, expected)
                    duplicate = next((i + 1 for i, call in enumerate(before[:-1])
                                      if call[0] == 'legal' and before[i + 1][0] == 'unlocked'), None)
                    if duplicate is not None:
                        before.pop(duplicate)
                    self.assertEqual(vm.calls, before)
                    self.assertEqual(vm.switches, 1)

    def test_upgrade_and_capacity_filter_unrelated_zero_level_and_zero_job_buildings(self):
        fixture = generated_fixture()
        names = ('eu5ab_candidate_replaces_existing_building', 'eu5ab_candidate_replaces_capacity_building')
        triggers = {name: parse(_blocks_for_token(fixture.triggers, '\n' + name + ' = ')[0])[0][2]
                    for name in (*names, *(n + '_worker_live' for n in names))}
        upgrades = cached_game_data()[2]
        vm = EligibilityVM({}, triggers)
        for building in [*fixture.catalog.buildings, 'unknown']:
            vm.building = building
            predecessors = upgrades.predecessors.get(building, ())
            for predecessor, level, jobs, permission in product(predecessors or ('unrelated',), (0, 1), (0, 100), (False, True)):
                vm.existing = [('unrelated', 1, 100, True), (predecessor, level, jobs, permission)]
                for name in names:
                    capacity = name == names[1]
                    expected = any(t in predecessors and n >= 1 and allowed and (not capacity or employment > 0)
                                   for t, n, employment, allowed in vm.existing)
                    vm.calls, vm.switches = [], 0
                    with self.subTest(building=building, row=vm.existing[-1], capacity=capacity):
                        self.assertEqual(vm.condition(triggers[name]), expected)
                        eligible = [t for t, n, employment, _ in vm.existing
                                    if t in predecessors and n >= 1 and (not capacity or employment > 0)]
                        self.assertTrue(all(t in eligible for kind, t in vm.calls if kind == 'upgrade_permission'))
