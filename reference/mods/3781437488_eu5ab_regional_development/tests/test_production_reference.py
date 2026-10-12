"""Static recipe identity and a directly supplied native efficiency scale."""
import unittest
from src.eu5autobuild import production_reference as reference
from tests._governor_script_vm import parse
from tests.test_market_supply_runtime import SupplyVM


class ReferenceSearchVM(SupplyVM):
    """Inject native market membership; execute emitted donor selection."""
    def __init__(self):
        super().__init__()
        self.definitions.update({k: v for k, _, v in parse(reference.render_candidate_effects(self.models))})
        self.stubs.pop('eu5ab_prepare_production_reference', None)
        self.market_members = {'market': ['location', 'second']}
        self.visited, self.filtered, self.estates = [], [], set()
        self.building_owners = {}

    def target(self, word, stack):
        if word == 'owner' and stack[-1] in self.building_owners:
            return self.building_owners[stack[-1]]
        return super().target(word, stack)

    def add_reference(self, location, building, *, market='market', owner='country'):
        self.owners[location] = owner
        self.location_markets[location] = market
        for members in self.market_members.values():
            if location in members:
                members.remove(location)
        self.market_members.setdefault(market, []).append(location)
        self.vars[location], self.lists[location] = {}, {}
        self.buildings[location] = [building]
        self.building_locations[building] = location
        self.building_types[building] = self.building_types['foundry']
        self.active_methods[building] = list(self.active_methods['foundry'])
        self.facts[building] = dict(self.facts['foundry'], building_level=1)
        self.efficiencies[location] = 2

    def value(self, word, stack):
        if word == 'owner' and stack[-1] in self.building_owners:
            return self.building_owners[stack[-1]]
        if word == 'estate_type':
            return 'estate:nobles' if stack[-1] in self.estates else None
        return super().value(word, stack)

    def test(self, key, operator, value, stack):
        if key == 'owner' and operator == '=' and not isinstance(value, list):
            # The native engine reports an invalid link for an unsafe owner
            # comparison, rather than silently filtering the unowned donor.
            if self.target('owner', stack) is None:
                raise AssertionError('unsafe comparison of an invalid owner')
        if key == 'has_building_with_at_least_one_level':
            self.filtered.append(stack[-1])
            return any(self.building_types[b] == 'building_type:' + value
                       and self.facts[b]['building_level'] > 0
                       for b in self.buildings.get(stack[-1], []))
        return super().test(key, operator, value, stack)

    def execute(self, entries, stack):
        index = 0
        while index < len(entries):
            key, _, body = entries[index]
            end = index + 1
            if key == 'if':
                while end < len(entries) and entries[end][0] in ('else_if', 'else'):
                    end += 1
            if key in ('every_owned_location', 'ordered_owned_location'):
                raise AssertionError('Reference lookup must not traverse the country')
            if key == 'ordered_location_in_market':
                fields = {k: v for k, _, v in body}
                pool = [location for location in self.market_members.get(stack[-1], [])
                        if self.condition(fields.get('limit', []), stack + [location])]
                pool.sort(key=lambda location: self.value(fields['order_by'], stack + [location]), reverse=True)
                for location in pool[:int(self.value(fields['max'], stack))]:
                    self.execute([entry for entry in body if entry[0] not in
                                  ('limit', 'order_by', 'max', 'check_range_bounds')], stack + [location])
            elif key == 'eu5ab_find_local_production_reference':
                self.visited.append(stack[-1])
                self.execute(self.definitions[key], stack)
            else:
                super().execute(entries[index:end], stack)
            index = end


class ProductionReferenceTests(unittest.TestCase):
    def test_unowned_destination_clears_old_reference_without_searching(self):
        vm = ReferenceSearchVM()
        vm.owners['location'] = None
        vm.vars['location']['eu5ab_quote_production_active'] = True
        vm.vars['location']['eu5ab_quote_production_search_reference'] = 'foundry'
        vm.run('eu5ab_prepare_production_reference')
        self.assertNotIn('eu5ab_pf_reference_building', vm.vars['location'])
        self.assertNotIn('eu5ab_quote_production_search_reference', vm.vars['location'])
        self.assertEqual(vm.visited, [])
        self.assertEqual(vm.filtered, [])

    def test_unowned_donors_are_safe_and_foreign_buildings_are_not_references(self):
        vm = ReferenceSearchVM()
        vm.add_reference('unowned', 'unowned_donor', owner=None)
        vm.add_reference('second', 'donor')
        vm.building_owners['foundry'] = None
        vm.building_owners['donor'] = 'foreign_country'
        vm.run('eu5ab_prepare_production_reference')
        self.assertNotIn('eu5ab_pf_reference_building', vm.vars['location'])
        self.assertEqual(vm.visited, ['location', 'second'])
        self.assertNotIn('unowned', vm.filtered)

    def test_owner_change_replaces_old_reference_and_uses_new_country(self):
        vm = ReferenceSearchVM()
        vm.add_reference('old_country', 'old_donor')
        vm.add_reference('new_country', 'new_donor', owner='new_owner')
        vm.owners['location'] = 'new_owner'
        vm.building_owners['foundry'] = 'country'
        vm.run('eu5ab_prepare_production_reference')
        self.assertEqual(vm.vars['location']['eu5ab_pf_reference_building'], 'new_donor')
        self.assertEqual(vm.visited, ['location', 'new_country'])

    def test_local_reference_does_not_search_market(self):
        vm = ReferenceSearchVM()
        vm.add_reference('second', 'donor')
        vm.run('eu5ab_prepare_production_reference')
        self.assertEqual(vm.vars['location']['eu5ab_pf_reference_building'], 'foundry')
        self.assertEqual(vm.visited, ['location'])
        self.assertEqual(vm.filtered, [])

    def test_fallback_visits_only_another_owned_location_in_destination_market(self):
        vm = ReferenceSearchVM()
        vm.add_reference('outside', 'outside_donor', market='other_market')
        vm.add_reference('foreign', 'foreign_donor', owner='foreign_country')
        vm.add_reference('second', 'donor')
        vm.active_methods['foundry'] = []  # Local type exists but is not usable.
        vm.run('eu5ab_prepare_production_reference')
        self.assertEqual(vm.vars['location']['eu5ab_pf_reference_building'], 'donor')
        self.assertEqual(vm.visited, ['location', 'second'])
        self.assertNotIn('outside', vm.filtered)
        self.assertNotIn('foreign', vm.filtered)

    def test_outside_market_reference_stays_unknown_without_blocking_pending_gate(self):
        vm = ReferenceSearchVM()
        vm.add_reference('second', 'donor', market='other_market')
        vm.facts['foundry']['building_level'] = 0
        vm.run('eu5ab_prepare_production_reference')
        self.assertNotIn('eu5ab_pf_reference_building', vm.vars['location'])
        self.assertEqual(vm.visited, ['location'])
        self.assertEqual(vm.filtered, [])
        kind = vm.scopes['eu5ab_candidate_building']
        self.assertTrue(vm.test('eu5ab_candidate_pending_allowed', '=', 'yes', [kind]))
        self.assertEqual(vm.value('eu5ab_candidate_pending_factor', [kind]), 1)
        for field in ('net_output_tools', 'net_input_iron'):
            self.assertEqual(vm.value('eu5ab_candidate_' + field, [kind]), 0)

    def test_unusable_first_matching_location_does_not_expand_search(self):
        for invalid in ('estate', 'recipe', 'efficiency'):
            with self.subTest(invalid=invalid):
                vm = ReferenceSearchVM()
                vm.add_reference('second', 'donor')
                vm.add_reference('third', 'later_donor')
                vm.facts['foundry']['building_level'] = 0
                if invalid == 'estate':
                    vm.estates.add('donor')
                elif invalid == 'recipe':
                    vm.active_methods['donor'] = []
                else:
                    vm.efficiencies['second'] = -1
                vm.run('eu5ab_prepare_production_reference')
                self.assertNotIn('eu5ab_pf_reference_building', vm.vars['location'])
                self.assertEqual(vm.visited, ['location', 'second'])

    def test_incremental_quantity_inherits_the_reference_without_a_level_formula(self):
        self.assertEqual(reference.capacity(2, 1, 5), 10)
        self.assertEqual(reference.capacity(2, 3, 5), 30)
        for values in ((2, -1, 1), (2, 1, float('inf')), (None, 1, 1)):
            with self.assertRaises(ValueError):
                reference.capacity(*values)

    def test_current_script_identity_refuses_missing_or_ambiguous_methods(self):
        vm = SupplyVM()
        building = 'mason'
        model = vm.models[building]
        vm.building_types['foundry'] = 'building_type:mason'
        triggers, values = reference.render({building: model}, ('masonry', 'stone', 'clay'))
        vm.capacity_triggers.update({k: v for k, _, v in parse(triggers)})
        vm.capacity_values.update({k: v for k, _, v in parse(values)})
        for method in model.slots[0]:
            vm.active_methods['foundry'] = ['production_method:' + method.production_method_id]
            self.assertTrue(vm.test('eu5ab_pr_recipe_known', '=', 'yes', ['foundry']))
            self.assertEqual(vm.value('eu5ab_pr_nominal_output_masonry', ['foundry']), method.outputs['masonry'])
        for methods in ([], ['production_method:unrecognized'],
                        ['production_method:' + m.production_method_id for m in model.slots[0]],
                        ['production_method:' + model.slots[0][0].production_method_id, 'production_method:unrecognized']):
            vm.active_methods['foundry'] = methods
            self.assertFalse(vm.test('eu5ab_pr_recipe_known', '=', 'yes', ['foundry']))

    def test_reference_uses_native_type_efficiency_and_only_incremental_levels(self):
        vm = SupplyVM()
        vm.efficiencies['location'] = 5
        self.assertEqual(vm.value('eu5ab_pr_reference_output_tools', ['foundry']), 10)
        vm.facts['foundry']['building_level'] = 20
        self.assertEqual(vm.value('eu5ab_pr_reference_output_tools', ['foundry']), 10)
        _, values = reference.render(vm.models, ('tools',))
        self.assertNotIn('goods_output', values)
        self.assertNotIn('every_buildings_in_location', values)
        self.assertNotIn('modifier:', values)
        self.assertNotIn('global_production_efficiency', values)


if __name__ == '__main__':
    unittest.main()
