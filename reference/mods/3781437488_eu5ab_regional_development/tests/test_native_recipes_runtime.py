"""Actual method identity overrides an economically preferable estimate."""
import re
import unittest

from src.eu5autobuild import native_recipes
from tests._game_data_fixtures import cached_game_data
from tests._governor_script_vm import parse
from tests.test_engine import RULES
from tests.test_production_runtime import ProductionVM
from tests.test_market_supply_runtime import SupplyVM


class ActiveVM(ProductionVM):
    def __init__(self, models):
        super().__init__(models, RULES)
        self.active = {}
        self.current = True

    def predicate(self, key, op, value):
        fields = {k: v for k, _, v in value} if isinstance(value, list) else {}
        if key == 'eu5ab_native_recipes_current':
            return self.current == (value == 'yes')
        if key == 'is_target_in_variable_list' and fields['name'] == 'eu5ab_native_recipe_types':
            return bool(self.active)
        if key == 'has_variable_map':
            return value in self.active
        if key == 'is_key_in_variable_map':
            return fields['name'] in self.active
        return super().predicate(key, op, value)

    def value(self, value):
        if isinstance(value, str) and '.variable_map(' in value:
            return self.active[re.search(r'variable_map\(([^|]+)', value)[1]]
        return super().value(value)


class CaptureVM(SupplyVM):
    def __init__(self):
        super().__init__()
        self.definitions.update({k: v for k, _, v in parse(native_recipes.render(self.models)[0])})
        self.capacity_triggers.update({k: v for k, _, v in parse(native_recipes.render(self.models)[1])})
        self.stubs.pop('eu5ab_clear_native_recipes')
        self.stubs.pop('eu5ab_refresh_native_recipes')
        self.scopes['eu5ab_native_recipe_building'] = 'foundry'

    def target(self, word, stack):
        if word.endswith('.building_type'):
            return 'building_type:' + self.building
        return super().target(word, stack)

    def value(self, value, stack):
        if isinstance(value, str) and value.startswith('production_method:'):
            return value
        return super().value(value, stack)


class NativeRecipeRuntimeTests(unittest.TestCase):
    def test_recipe_identity_has_no_gui_reader(self):
        from tests._generated import generated_fixture
        self.assertEqual(native_recipes.render(cached_game_data()[0])[2], '')
        from src.eu5autobuild.construction_slots import capture_widget
        widget = capture_widget('contract')
        self.assertNotIn('Building.GetProductionMethods', widget)
        self.assertNotIn('eu5ab_gui_native_recipe', generated_fixture().scripted_guis)
        self.assertIn('every_production_method_of_building', generated_fixture().effects)

    def test_cheaper_later_recipe_wins_estimate_but_active_starved_recipe_wins_capture(self):
        models = cached_game_data()[0]
        vm = ActiveVM({'mason': models['mason']})
        vm.building = 'mason'
        vm.prices = {'stone': 9, 'clay': 1, 'masonry': 20}
        self.assertEqual(vm.value('eu5ab_recipe_mason_0_selected'), 2)
        vm.active['eu5ab_native_recipe_slot_0'] = 1
        vm.short_goods = {'stone'}
        self.assertEqual(vm.value('eu5ab_recipe_mason_0_selected'), 1)
        self.assertFalse(vm.available())
        vm.current = False
        self.assertEqual(vm.value('eu5ab_recipe_mason_0_selected'), 2)

    def test_variable_output_estimate_does_not_prove_target_good(self):
        models = cached_game_data()[0]
        building = next(k for k, model in models.items() if any(
            any('tools' in m.outputs for m in slot) and any('tools' not in m.outputs for m in slot)
            for slot in model.slots))
        vm = ActiveVM({building: models[building]})
        vm.building = building
        vm.prices['tools'] = 1000
        vm.advances = {a for slot in models[building].slots for m in slot for a in m.unlock_advances}
        good = 'eu5ab_recipe_guarantees_tools'
        self.assertTrue(vm.condition(vm.triggers['eu5ab_recipe_produces_tools']))
        self.assertFalse(vm.condition(vm.triggers[good]))
        for i, slot in enumerate(models[building].slots):
            vm.active[f'eu5ab_native_recipe_slot_{i}'] = vm.value(f'eu5ab_recipe_{building}_{i}_selected')
        self.assertTrue(vm.condition(vm.triggers[good]))
        vm.current = False
        self.assertFalse(vm.condition(vm.triggers[good]))

    def test_capture_requires_every_slot_and_rejects_conflicting_buildings(self):
        vm = CaptureVM()
        vm.building = 'fine_cloth_guild'
        model = vm.models[vm.building]
        key = 'building_type:' + vm.building
        vm.run('eu5ab_clear_native_recipes')
        vm.scopes['eu5ab_native_recipe_method'] = 'production_method:' + model.slots[0][0].production_method_id
        vm.run('eu5ab_capture_native_recipe_method')
        self.assertNotIn(key, vm.lists['location'].get('eu5ab_native_recipe_types', []))
        for slot in model.slots[1:]:
            vm.scopes['eu5ab_native_recipe_method'] = 'production_method:' + slot[0].production_method_id
            vm.run('eu5ab_capture_native_recipe_method')
        self.assertIn(key, vm.lists['location']['eu5ab_native_recipe_types'])
        vm.scopes['eu5ab_native_recipe_method'] = 'production_method:' + model.slots[0][1].production_method_id
        vm.run('eu5ab_capture_native_recipe_method')
        vm.vars['location']['eu5ab_native_recipe_capturing'] = True
        vm.run('eu5ab_finish_native_recipe_capture')
        self.assertNotIn(key, vm.lists['location']['eu5ab_native_recipe_types'])
        vm.run('eu5ab_clear_native_recipes')
        self.assertFalse(vm.variable_maps['location'].get('eu5ab_native_recipe_slot_0'))

    def test_script_refresh_reads_current_methods_without_callbacks(self):
        vm = CaptureVM()
        vm.building = 'fine_cloth_guild'
        vm.building_types['foundry'] = 'building_type:fine_cloth_guild'
        model = vm.models[vm.building]
        key = 'building_type:' + vm.building
        vm.active_methods['foundry'] = ['production_method:' + slot[0].production_method_id
                                        for slot in model.slots]
        vm.run('eu5ab_refresh_native_recipes')
        self.assertIn(key, vm.lists['location']['eu5ab_native_recipe_types'])
        self.assertEqual(vm.variable_maps['location']['eu5ab_native_recipe_slot_0'][key], 1)
        vm.active_methods['foundry'][0] = 'production_method:' + model.slots[0][1].production_method_id
        vm.run('eu5ab_refresh_native_recipes')
        self.assertEqual(vm.variable_maps['location']['eu5ab_native_recipe_slot_0'][key], 2)
        vm.active_methods['foundry'].pop()
        vm.run('eu5ab_refresh_native_recipes')
        self.assertNotIn(key, vm.lists['location']['eu5ab_native_recipe_types'])
        # Never add the quantities of multiple alternatives as active output.
        vm.active_methods['foundry'] = ['production_method:' + m.production_method_id
                                       for slot in model.slots for m in slot]
        vm.run('eu5ab_refresh_native_recipes')
        self.assertNotIn(key, vm.lists['location']['eu5ab_native_recipe_types'])

    def test_active_capture_filter_includes_destination_and_upgrade_predecessor(self):
        models, _, upgrades, _ = cached_game_data()
        destination = next(
            building for building in sorted(models)
            if upgrades.predecessors.get(building)
        )
        predecessor = upgrades.predecessors[destination][0]
        trigger = native_recipes.render_active_filter_trigger(models, upgrades)
        predecessor_case = trigger.split(
            f'building_type:{predecessor} = {{', 1
        )[1].split('\n\t\t}', 1)[0]
        self.assertIn(
            f'target = building_type:{destination}', predecessor_case
        )
        effects = native_recipes.render(models, upgrades)[0]
        self.assertIn('eu5ab_active_recipe_catalog_current = yes', effects)
        self.assertIn('eu5ab_native_recipe_relevant_to_active_catalog = yes', effects)


if __name__ == '__main__':
    unittest.main()
