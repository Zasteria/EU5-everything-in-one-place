"""Save method names, slot identity and economic association regressions."""
import unittest

from src.eu5autobuild.save_production import associate_recipe, identify_saved_methods
from tests._game_data_fixtures import cached_game_data
from tests.test_native_recipes_runtime import ActiveVM


JEWELRY = b'''\n\ttype=jewelry_guild
\tvariables={
\t\tgold_base={}
\t}
\tgold_base={
\t\tmissing={
\t\t\tdemand=gold_base
\t\t}
\t}
\tgems_enhancement={
\t\tmissing={
\t\t\tdemand=gems_enhancement
\t\t}
\t}
'''


class SaveProductionTests(unittest.TestCase):
    def setUp(self):
        self.model = cached_game_data()[0]['jewelry_guild']

    def test_names_without_maintenance_and_nested_names_use_exact_configured_slots(self):
        result = identify_saved_methods(JEWELRY, self.model)
        self.assertEqual(result['status'], 'configured_saved_methods')
        self.assertEqual(result['methods'], ['gold_base', 'gems_enhancement'])
        self.assertEqual(result['slots'], [['gold_base'], ['gems_enhancement']])
        linked = associate_recipe(result, self.model, dict(jewelry=4, goods_gold=2, gems=3), saved_profit=.39785)
        self.assertEqual(linked['declared_outputs'], {'jewelry': 1.1})
        self.assertEqual(linked['declared_inputs'], {'goods_gold': .5208, 'gems': .1042})
        self.assertAlmostEqual(linked['declared_output_value'], 4.4)
        self.assertAlmostEqual(linked['declared_input_cost'], .5208 * 2 + .1042 * 3)
        self.assertAlmostEqual(linked['declared_gross_margin'], 4.4 - .5208 * 2 - .1042 * 3)
        self.assertEqual(linked['saved_last_months_profit'], .39785)

        vm = ActiveVM({'jewelry_guild': self.model})
        vm.building = 'jewelry_guild'
        vm.prices = dict(jewelry=4, goods_gold=2, gems=3)
        for index, slot in enumerate(self.model.slots):
            vm.active[f'eu5ab_native_recipe_slot_{index}'] = next(
                i for i, method in enumerate(slot, 1)
                if method.production_method_id in result['slots'][index])
        self.assertAlmostEqual(vm.value('eu5ab_recipe_expected_output_value'), 4.4)
        self.assertAlmostEqual(vm.value('eu5ab_recipe_expected_input_cost'), .5208 * 2 + .1042 * 3)

    def test_missing_price_is_unknown_and_does_not_replace_saved_profit(self):
        result = associate_recipe(identify_saved_methods(JEWELRY, self.model), self.model,
                                  dict(jewelry=4, goods_gold=2), saved_profit=.39785)
        self.assertIsNone(result['declared_input_cost'])
        self.assertIsNone(result['declared_gross_margin'])
        self.assertEqual(result['saved_last_months_profit'], .39785)

    def test_conflict_missing_or_unrecognized_slots_are_never_valued_as_zero(self):
        for block, model, status in (
            (JEWELRY + b'\tsilver_base={\n\t}\n', self.model, 'conflicting_slot'),
            (b'\tgold_base={\n\t}\n', self.model, 'missing_saved_slot'),
            (JEWELRY + b'\tforeign_recipe={\n\t\tdemand=foreign_recipe\n\t}\n', self.model, 'unrecognized_saved_method'),
            (JEWELRY, None, 'unresolved_configuration'),
        ):
            with self.subTest(status=status):
                identified = identify_saved_methods(block, model)
                self.assertEqual(identified['status'], status)
                result = associate_recipe(identified, model, {}, saved_profit=-2)
                self.assertIsNone(result['declared_outputs'])
                self.assertIsNone(result['declared_gross_margin'])
                self.assertEqual(result['saved_last_months_profit'], -2)
