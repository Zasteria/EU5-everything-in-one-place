"""Native upgrade readings cross the real snapshot, reservation and job paths."""
from copy import deepcopy
from dataclasses import replace
import re
import unittest

from src.eu5autobuild import queued_workforce, upgrade_queue
from tests._game_data_fixtures import cached_game_data
from tests._governor_script_vm import parse
from tests.test_market_supply_runtime import SupplyVM


class UpgradeQueueVM(SupplyVM):
    def __init__(self):
        super().__init__()
        _, _, self.upgrades, self.workforce = cached_game_data()
        effects, triggers, values, guis = upgrade_queue.render(self.upgrades)
        self.definitions.update({k: v for k, _, v in parse(effects)})
        self.capacity_triggers.update({k: v for k, _, v in parse(triggers)})
        self.capacity_values.update({k: v for k, _, v in parse(values + queued_workforce.render(self.workforce, self.upgrades))})
        self.callback = dict((k, v) for k, _, v in parse(re.sub(r'saved_scopes = \{[^}]*\}', '', guis))[0][2])['effect']
        self.buildings['location'] = ['old', 'new']
        self.building_types.update(old='building_type:weapon_guild', new='building_type:weapon_workshop')
        self.building_locations.update(old='location', new='location')
        self.facts.update(old=dict(building_level=3, building_levels_under_construction=0),
                          new=dict(building_level=0, building_levels_under_construction=1))
        self.vars.update(old={}, new={})
        self.lists.update(old={}, new={})
        self.native.update(num_civil_constructions=1, eu5ab_scan_month_current=True, eu5ab_rgo_queued_jobs=0)
        self.vars[self.ROOT].update(eu5ab_scan_active=1, eu5ab_scan_month=7, eu5ab_scan_year=1436)
        self.vars['location'].update(eu5ab_capacity_requested=1, eu5ab_capacity_request=7,
                                    eu5ab_capacity_worker_country=self.ROOT, eu5ab_capacity_month=7, eu5ab_capacity_year=1436)
        self.lists[self.ROOT]['eu5ab_worker_pending_locations'] = ['location']
        self.run('eu5ab_request_upgrade_snapshot')

    def value(self, word, stack):
        if isinstance(word, str) and word.startswith('variable_map('):
            name, key = word[len('variable_map('):-1].split('|', 1)
            target = self.value(key, stack)
            if target not in self.variable_maps.get(stack[-1], {}).get(name, {}):
                raise AssertionError('Reading an unset native variable map entry')
        if word == 'prev.building_level':
            return self.facts[stack[-2]]['building_level']
        if word == 'building_type.employment_size':
            return self.workforce.all_buildings[self.building_types[stack[-1]].removeprefix('building_type:')].jobs_per_level / 1000
        return super().value(word, stack)

    def test(self, key, op, value, stack):
        if key == 'is_key_in_variable_map':
            fields = dict((k, v) for k, _, v in value)
            if fields['name'] not in self.variable_maps.get(stack[-1], {}):
                raise AssertionError('Checking keys of an absent native variable map')
        if key == 'trigger_if':
            limit = next(body for name, _, body in value if name == 'limit')
            return not self.condition(limit, stack) or self.condition(
                [entry for entry in value if entry[0] != 'limit'], stack)
        if key == 'any_buildings_in_location':
            return any(self.condition(value, stack + [building]) for building in self.buildings.get(stack[-1], []))
        if key == 'building_type' and isinstance(value, str):
            return value == self.building_types[stack[-1]]
        return super().test(key, op, value, stack)

    def capture(self, count, ticket=7):
        self.scopes.update(eu5ab_engine_upgrade_reserved=count, eu5ab_capacity_ticket=ticket)
        self.execute(self.callback, ['old'])

    def available(self):
        return self.test('eu5ab_upgrade_source_available', '=', 'yes', ['old'])


class UpgradeQueueTests(unittest.TestCase):
    def test_partial_exhausted_zero_and_invalid_native_readings(self):
        vm = UpgradeQueueVM()
        self.assertFalse(vm.available())
        for count, available in ((1, True), (3, False), (0, True), (-1, False), (4, False)):
            vm.capture(count)
            if count == 0:
                vm.variable_maps['location'].pop('eu5ab_upgrade_reserved_levels', None)
            self.assertEqual(vm.available(), available)
            if count >= 0 and count <= 3:
                self.assertEqual(vm.value('eu5ab_upgrade_reserved_count', ['old']), count)
        vm.native['num_civil_constructions'] = 0
        self.assertTrue(vm.available())

    def test_old_ticket_owner_change_and_new_scan_cannot_reuse_credit(self):
        vm = UpgradeQueueVM()
        vm.capture(1)
        before = deepcopy(vm.variable_maps)
        vm.capture(3, ticket=6)
        self.assertEqual(vm.variable_maps, before)
        vm.owners['location'] = 'other'
        self.assertFalse(vm.available())
        vm.owners['location'] = vm.ROOT
        vm.native['num_civil_constructions'] = 2
        self.assertFalse(vm.available())
        vm.native['num_civil_constructions'] = 1
        vm.facts['old']['building_level'] = 2
        self.assertFalse(vm.available())
        vm.facts['old']['building_level'] = 3
        vm.run('eu5ab_request_upgrade_snapshot')
        self.assertFalse(vm.available())
        # Native GUI inspection can evaluate all trigger siblings. Even then
        # the guarded comparisons must not read missing map event targets.
        location_checks = vm.capacity_triggers['eu5ab_upgrade_source_sampled'][0][2]
        results = [vm.test(k, op, value, ['old', 'location'])
                   for k, op, value in location_checks]
        self.assertFalse(all(results))

    def test_upgrade_jobs_are_net_and_roads_do_not_change_the_credit(self):
        vm = UpgradeQueueVM()
        source = vm.workforce.all_buildings['weapon_guild']
        target = vm.workforce.all_buildings['weapon_workshop']
        pop = target.pop_types[0]
        full = target.jobs_per_level / 1000
        name = 'eu5ab_queued_jobs_' + pop
        self.assertEqual(vm.value(name, ['location']), full)  # Unknown is conservative.
        vm.capture(1)
        self.assertAlmostEqual(vm.value(name, ['location']), max(0, full - source.jobs_per_level / 1000))
        vm.native['num_civil_constructions'] = 2  # One ordinary expansion plus the upgrade.
        vm.facts['new']['building_levels_under_construction'] = 2
        vm.capture(1)
        self.assertAlmostEqual(vm.value(name, ['location']), 2 * full - source.jobs_per_level / 1000)
        vm.native['num_civil_constructions'] = 3  # A road adds no building jobs.
        vm.capture(1)
        self.assertAlmostEqual(vm.value(name, ['location']), 2 * full - source.jobs_per_level / 1000)
        vm.facts['new']['building_levels_under_construction'] = 1  # Cancel upgrade; keep expansion.
        vm.native['num_civil_constructions'] = 2
        vm.capture(0)
        self.assertEqual(vm.value(name, ['location']), full)

    def test_unmodeled_or_different_profession_successor_has_no_false_transfer(self):
        for target in ('unmodeled', 'iron_foundry'):
            vm = UpgradeQueueVM()
            altered = replace(vm.upgrades, native_successors={'weapon_guild': ('weapon_workshop', target)})
            vm.capacity_values.update({k: v for k, _, v in parse(queued_workforce.render(vm.workforce, altered))})
            vm.buildings['location'].append('other_target')
            vm.building_types['other_target'] = 'building_type:' + target
            vm.building_locations['other_target'] = 'location'
            vm.facts['other_target'] = dict(building_level=0, building_levels_under_construction=1)
            vm.capture(1)
            self.assertEqual(vm.value('eu5ab_queued_jobs_burghers', ['location']), .1)
