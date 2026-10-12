"""Execute market reservations, native pending reconciliation and target gates."""
import re
import unittest
from functools import cache

from src.eu5autobuild.market_supply import render, uncovered
from tests._game_data_fixtures import cached_game_data
from tests._generated import generated_fixture
from tests._governor_script_vm import parse
from tests.test_engine import RULES
from tests.test_queue_recovery_runtime import QueueVM


@cache
def supply_scripts():
    data = cached_game_data()
    return tuple({k: v for k, _, v in parse(text)} for text in render(data[0], RULES, data[2]))


class SupplyVM(QueueVM):
    def __init__(self):
        self.facts = {}
        self.building_types = {'foundry': 'building_type:iron_foundry'}
        self.building_locations = {'foundry': 'location'}
        fixture = generated_fixture()
        super().__init__(fixture.effects, fixture.scripted_guis)
        self.models = cached_game_data()[0]
        from src.eu5autobuild.production_reference import render as reference
        self.capacity_triggers.update({k: v for k, _, v in parse(reference(self.models, ())[0])})
        self.active_methods = {'foundry': [
            'production_method:' + slot[0].production_method_id
            for slot in self.models['iron_foundry'].slots]}
        self.stubs['trigger_event_silently'] = lambda: None
        effects, triggers, values = supply_scripts()
        self.definitions.update(effects)
        self.capacity_values.update(values)
        self.capacity_triggers.update(triggers)
        for name in ('eu5ab_reserve_candidate_output', 'eu5ab_release_candidate_output'):
            self.stubs.pop(name)
        self.stubs.pop('eu5ab_refresh_build_pending')
        self.stubs.pop('eu5ab_ensure_build_pending')
        for name in ('eu5ab_pl_today', 'eu5ab_candidate_pending_data_ready'):
            self.native.pop(name)
        self.owners['second'] = self.ROOT
        self.vars.update(second={}, foundry={}, **{'building_type:iron_foundry': {}})
        self.lists.update(second={}, foundry={}, **{'building_type:iron_foundry': {}})
        self.buildings = {'location': ['foundry'], 'second': []}
        self.facts = {'foundry': dict(building_level=2, building_levels_under_construction=1,
                                     building_employed_amount=500, building_employment_size_amount=1000)}
        self.demands, self.supplies = {'iron': 10, 'tools': 10}, {'iron': 5, 'tools': 5}
        self.location_markets = {'location': 'market', 'second': 'market'}
        self.scopes['eu5ab_candidate_building'] = 'building_type:iron_foundry'
        self.native.pop('eu5ab_candidate_pending_allowed', None)
        self.native.pop('eu5ab_candidate_has_direct_output', None)
        self.native['eu5ab_candidate_produces_food'] = False
        self.native['eu5ab_food_emergency_enabled'] = False
        self.proposed = {'output': {'tools': 10}, 'input': {'iron': 5}}
        self.produced_good = 'goods:tools'
        self.efficiencies = {'location': 1, 'second': 1}
        self.vars[self.ROOT]['eu5ab_global_job_fill_deadline_months'] = 12
        self.vars['location']['eu5ab_pf_reference_building'] = 'foundry'

    def ledger_set(self, building, field, value):
        self.variable_maps.setdefault(self.building_locations[building], {}).setdefault(field, {})[building] = value

    def ledger_get(self, building, field, default=None):
        return self.variable_maps.get(self.building_locations[building], {}).get(field, {}).get(building, default)

    def ledger_remove(self, building, field):
        self.variable_maps.get(self.building_locations[building], {}).get(field, {}).pop(building, None)

    def ledger_clear(self, building, prefix='eu5ab_pl_'):
        for name, mapping in self.variable_maps.get(self.building_locations[building], {}).items():
            if name.startswith(prefix):
                mapping.pop(building, None)

    def target(self, word, stack):
        word = word.strip('"')
        if word.startswith('variable_map('):
            return self.value(word, stack)
        if '.' in word:
            first, remainder = word.split('.', 1)
            if first.startswith(('scope:', 'var:')) or first in ('location', 'owner', 'prev'):
                target = self.target(first, stack)
                return None if target is None else self.target(remainder, stack + [target])
        if word == 'owner' and stack[-1] in self.building_locations:
            return self.owners.get(self.building_locations[stack[-1]])
        if word.endswith('.produced_goods'):
            return self.produced_good
        if word == 'location':
            return self.building_locations.get(stack[-1])
        if word.startswith('prev.'):
            return self.target(word[5:], stack[:-1])
        if word == 'location.owner':
            return self.owners.get(self.building_locations.get(stack[-1]))
        if word == 'market':
            return self.location_markets.get(stack[-1], 'market')
        if word.endswith('.market'):
            return self.location_markets.get(self.target(word[:-7], stack))
        if word.endswith('.owner'):
            return self.owners.get(self.target(word[:-6], stack))
        if word == 'building_type':
            return self.building_types.get(stack[-1])
        return super().target(word, stack)

    def value(self, value, stack):
        if isinstance(value, list):
            if any(k == 'switch' for k, _, _ in value):
                raise AssertionError('EU5 script values do not support switch')
            result = 0
            if any(k in ('every_buildings_in_location', 'building_type', 'location', 'location.owner') for k, _, _ in value):
                for k, op, body in value:
                    if k == 'every_buildings_in_location':
                        fields = {a: c for a, _, c in body}
                        for building in self.buildings.get(stack[-1], []):
                            if self.condition(fields.get('limit', []), stack + [building]):
                                result = self.value([('value', '=', str(result)), *(e for e in body if e[0] != 'limit')], stack + [building])
                    elif k in ('building_type', 'location', 'location.owner'):
                        result = self.value([('value', '=', str(result)), *body], stack + [self.target(k, stack)])
                    else:
                        result = super().value([('value', '=', str(result)), (k, op, body)], stack)
                return result
        if isinstance(value, str):
            value = value.strip('"')
            if 'building_efficiency(building_type:' in value:
                source = value.split('.building_efficiency(')[0]
                return self.efficiencies[self.target(source, stack)]
            if '.' in value and value.rsplit('.', 1)[-1] in self.capacity_values:
                source, name = value.rsplit('.', 1)
                return self.value(self.capacity_values[name], stack + [self.target(source, stack)])
            if value.endswith('.produced_goods'):
                return self.target(value, stack)
            if stack[-1] in self.building_locations and value.startswith(('var:', 'variable_map(')):
                raise AssertionError('Building scopes cannot read persistent variables')
            if value.startswith('prev.') and value[5:] in self.capacity_values:
                return self.value(value[5:], stack[:-1])
            if value == 'eu5ab_pending_profit_rank':
                return self.value(self.capacity_values[value], stack)
            if value in ('location', 'location.owner', 'building_type') or value.startswith('prev.'):
                return self.target(value, stack)
            if value == 'owner' and stack[-1] in self.building_locations:
                return self.owners[self.building_locations[stack[-1]]]
            if value.startswith(('scope:', 'location.', 'owner.')) and '.' in value and value.rsplit('.', 1)[1] in self.facts.get(self.target(value.rsplit('.', 1)[0], stack), {}):
                source, fact = value.rsplit('.', 1)
                return self.facts[self.target(source, stack)][fact]
            if value == 'estate_type':
                return None
            if value.startswith('production_method:'):
                return value
            for kind in ('output', 'input'):
                prefix = f'eu5ab_proposed_{kind}_'
                if value.startswith(prefix):
                    return self.proposed[kind].get(value[len(prefix):], 0)
            if value.startswith('eu5ab_recipe_guarantees_'):
                return True  # Native identity fixture; recipe bridge has separate tests.
            if value.startswith('default_price('):
                return 1
            if value == 'market' or value.endswith('.market'):
                return self.target(value, stack)
            if value in self.facts.get(stack[-1], {}):
                return self.facts[stack[-1]][value]
            if value.startswith(('building_type:', 'goods:')):
                return value
            if '.variable_map(' in value:
                target, expression = value.split('.variable_map(', 1)
                return self.value('variable_map(' + expression, stack + [self.target(target, stack)])
            if 'goods_demand_in_market' in value or 'goods_supply_in_market' in value:
                good = re.search(r'goods:(\w+)', value)[1]
                return (self.demands if 'demand' in value else self.supplies).get(good, 0)
        return super().value(value, stack)

    def test(self, k, op, v, stack):
        if k == 'building_efficiency':
            fields = {a: (b, c) for a, b, c in v}
            op, threshold = fields['value']
            actual = self.efficiencies.get(stack[-1])
            return actual is not None and {'>=': actual >= self.value(threshold, stack), '>': actual > self.value(threshold, stack), '=': actual == self.value(threshold, stack)}[op]
        if k == 'is_full_capacity':
            facts = self.facts[stack[-1]]
            return (facts['building_employed_amount'] >= facts['building_employment_size_amount']) == (v == 'yes')
        if k == 'switch':
            fields = {a: c for a, _, c in v}
            return self.condition(fields.get(self.value(fields['trigger'], stack),
                                             fields.get('fallback', [])), stack)
        if k == 'any_production_method_of_building':
            return any(self.condition(v, stack + [method])
                       for method in self.active_methods.get(stack[-1], []))
        if 'variable_map(' in k and isinstance(v, list):
            target = self.value(k.strip('"'), stack)
            return target in self.building_locations and self.condition(v, stack + [target])
        if k == 'exists' and v == 'this':
            return stack[-1] in self.vars or stack[-1] in self.building_locations
        if k == 'is_opened':
            return self.facts[stack[-1]].get('is_opened', True) == (v == 'yes')
        if stack[-1] in self.building_locations and k in ('has_variable', 'has_variable_map', 'has_variable_list',
                                                         'is_key_in_variable_map', 'is_target_in_variable_list'):
            raise AssertionError('Building scopes cannot test persistent variables')
        if k == 'always':
            return v == 'yes'
        if k == 'variable_list_size':
            fields = {a: c for a, _, c in v}
            if 'target' in fields:
                raise AssertionError('variable_list_size uses value')
            return len(self.lists[stack[-1]].get(fields['name'], [])) == self.value(fields['value'], stack)
        if k == 'building_produced_goods':
            return v == 'goods:tools'
        if k in ('location', 'location.owner') and isinstance(v, list):
            return self.condition(v, stack + [self.target(k, stack)])
        return super().test(k, op, v, stack)

    def execute(self, entries, stack):
        if len(entries) == 1 and entries[0][0].startswith('variable_map('):
            return self.execute(entries[0][2], stack + [self.value(entries[0][0], stack)])
        for k, _, v in entries:
            if stack[-1] in self.building_locations and k in ('set_variable', 'remove_variable', 'change_variable',
                    'add_to_variable_map', 'remove_from_variable_map', 'clear_variable_map', 'add_to_variable_list', 'clear_variable_list'):
                raise AssertionError('Building scopes cannot write persistent variables')
            if k == 'add_to_variable_map' and isinstance(dict((a, c) for a, _, c in v)['value'], list):
                raise AssertionError('Map writes cannot contain inline formulas')
        if len(entries) == 1 and entries[0][0] == 'every_production_method_of_building':
            body = entries[0][2]
            fields = {a: c for a, _, c in body}
            for method in self.active_methods.get(stack[-1], []):
                if self.condition(fields.get('limit', []), stack + [method]):
                    self.execute([e for e in body if e[0] != 'limit'], stack + [method])
            return
        if len(entries) == 1 and entries[0][0] in ('every_buildings_in_location', 'building_type', 'location', 'location.owner'):
            k, _, body = entries[0]
            if k in ('building_type', 'location', 'location.owner'):
                return self.execute(body, stack + [self.target(k, stack)])
            fields = {a: c for a, _, c in body}
            for building in self.buildings.get(stack[-1], []):
                if self.condition(fields.get('limit', []), stack + [building]):
                    self.execute([e for e in body if e[0] != 'limit'], stack + [building])
            return
        # QueueVM's loop dispatches each node to its base; handle these scopes
        # wherever they appear without splitting if/else chains.
        if any(k in ('every_buildings_in_location', 'every_production_method_of_building', 'building_type', 'location', 'location.owner') or k.startswith('variable_map(') for k, _, _ in entries):
            batch = []
            for entry in entries:
                if entry[0] in ('every_buildings_in_location', 'every_production_method_of_building', 'building_type', 'location', 'location.owner') or entry[0].startswith('variable_map('):
                    super().execute(batch, stack)
                    self.execute([entry], stack)
                    batch = []
                else:
                    batch.append(entry)
            return super().execute(batch, stack)
        return super().execute(entries, stack)


class MarketSupplyRuntimeTests(unittest.TestCase):
    def test_reservations_share_market_and_release_original_snapshot(self):
        vm = SupplyVM()
        vm.run('eu5ab_refresh_build_pending', vm.ROOT)
        quantity = 2
        before = vm.value('eu5ab_market_pending_tools', ['location'])
        vm.run('eu5ab_reserve_candidate_output')
        self.assertEqual(vm.value('eu5ab_market_pending_tools', ['location']), before + quantity)
        vm.scopes['eu5ab_candidate_location'] = 'second'
        self.assertEqual(vm.value('eu5ab_market_pending_tools', ['second']), before + quantity)
        vm.scopes['eu5ab_candidate_location'] = 'location'
        vm.lists['location']['eu5ab_q_approved_types'] = ['building_type:iron_foundry']
        self.assertEqual(vm.value('eu5ab_market_pending_tools', ['location']), before)
        vm.location_markets['location'] = 'other_market'
        vm.run('eu5ab_release_candidate_output')
        self.assertEqual(vm.variable_maps[vm.ROOT]['eu5ab_build_pending_tools']['market'], before)

    def test_no_more_projects_when_pending_covers_gap_and_unknown_rgo_blocks(self):
        vm = SupplyVM()
        vm.run('eu5ab_refresh_build_pending', vm.ROOT)
        country_maps = vm.variable_maps[vm.ROOT]
        country_maps['eu5ab_build_future_input_iron'] = {}
        country_maps['eu5ab_build_pending_iron'] = {'market': 6}
        self.assertFalse(vm.test('eu5ab_market_needs_iron', '=', 'yes', ['location']))
        country_maps['eu5ab_build_pending_iron']['market'] = 2
        country_maps['eu5ab_rgo_pending_output_iron'] = {'market': 4}
        self.assertFalse(vm.test('eu5ab_market_needs_iron', '=', 'yes', ['location']))
        country_maps['eu5ab_rgo_pending_output_iron']['market'] = 0
        self.assertTrue(vm.test('eu5ab_market_needs_iron', '=', 'yes', ['location']))
        country_maps['eu5ab_rgo_pending_unknown_iron'] = {'market': 1}
        self.assertFalse(vm.test('eu5ab_market_needs_iron', '=', 'yes', ['location']))
        vm.demands['iron'] = 0
        self.assertFalse(vm.test('eu5ab_market_needs_iron', '=', 'yes', ['location']))

    def test_reference_boundaries(self):
        self.assertEqual(uncovered(10, 10, 1), 0)
        self.assertEqual(uncovered(0, 0, 0), 0)
        self.assertEqual(uncovered(10, 0, 0, unknown=True), 0)

    def test_legacy_ticket_cannot_block_an_unknown_new_project(self):
        vm = SupplyVM()
        vm.vars['location'].pop('eu5ab_pf_reference_building')
        vm.lists[vm.ROOT]['eu5ab_pl_tickets'] = [12345]
        vm.run('eu5ab_prepare_candidate_dependencies')
        self.assertNotIn('eu5ab_q_dependency_wait', vm.vars['location'])
        self.assertNotIn('eu5ab_q_waiting_data', vm.vars[vm.ROOT])


if __name__ == '__main__':
    unittest.main()
