"""Equivalent screening results with fewer repeated building-type lookups."""
from itertools import product
from decimal import Decimal
import unittest

from tests._generated import generated_fixture
from tests._game_data_fixtures import cached_game_data
from tests._governor_script_vm import parse
from tests.test_candidate_score_optimizations import ScoreVM
from tests.test_construction_batch_runtime import BatchVM
from tests.test_engine import RULES
from tests.test_production_runtime import ProductionVM


class ScreeningDispatchTests(unittest.TestCase):
    def test_material_snapshot_all_types_zero_unknown_and_stale_keys(self):
        fixture = generated_fixture()
        demands = cached_game_data()[1]
        materials = sorted({g for d in demands.values() for g, n in d.goods.items() if n > 0})
        values = {k: v for k, _, v in parse(fixture.values) if k.startswith('eu5ab_construction_demand_')}
        reader = ScoreVM(values, {})
        vm = BatchVM()
        for building in [*demands, 'unknown']:
            reader.building = building
            kind = 'building_type:' + building
            vm.scopes['eu5ab_candidate_building'] = kind
            maps = vm.variable_maps.setdefault('location', {})
            for good in materials:
                maps['eu5ab_quote_material_' + good] = {kind: 999, 'another_type': 777}
            vm.run('eu5ab_batch_snapshot_quote_materials', 'location')
            for good in materials:
                amount = demands[building].goods.get(good, 0) if building in demands else 0
                expected = Decimal(f'{max(0, amount):g}')
                with self.subTest(building=building, good=good):
                    self.assertEqual(Decimal(str(reader.value('eu5ab_construction_demand_' + good))), expected)
                    self.assertEqual(maps['eu5ab_quote_material_' + good].get(kind, 0), expected)
                    self.assertEqual(maps['eu5ab_quote_material_' + good]['another_type'], 777)
                    if expected == 0:
                        self.assertNotIn(kind, maps['eu5ab_quote_material_' + good])
            # Repeated capture must replace, rather than accumulate, quantities.
            previous = {g: maps['eu5ab_quote_material_' + g].copy() for g in materials}
            vm.run('eu5ab_batch_snapshot_quote_materials', 'location')
            self.assertEqual(previous, {g: maps['eu5ab_quote_material_' + g] for g in materials})

    def test_input_dispatch_preserves_availability_first_and_optional_shortage(self):
        models = cached_game_data()[0]
        vm = ProductionVM(models, RULES)
        reference = parse('reference = { eu5ab_recipe_available = yes OR = { '
                          'scope:eu5ab_candidate_location.owner.var:eu5ab_global_stop_input_shortage <= 0 '
                          'NOT = { eu5ab_candidate_scoring_input_shortage = yes } } }')[0][2]
        reads = []
        predicate = vm.predicate

        def watched(key, op, value):
            if key.startswith('eu5ab_recipe_') and key.endswith('_inputs'):
                reads.append(key)
            return predicate(key, op, value)

        vm.predicate = watched
        for building in [*models, 'unknown']:
            vm.building = building
            for stop, shortage, selection in product((0, 1), (False, True), (0, 1, -1, 99)):
                vm.variables['eu5ab_global_stop_input_shortage'] = stop
                vm.short_goods = set(RULES.input_goods) if shortage else set()
                for index, slot in enumerate(models[building].slots if building in models else ()):
                    vm.native_values[f'eu5ab_recipe_{building}_{index}_selected'] = len(slot) if selection == -1 else selection
                reads.clear()
                expected = vm.condition(reference)
                expected_reads = reads.copy()
                reads.clear()
                with self.subTest(building=building, stop=stop, shortage=shortage, selection=selection):
                    self.assertEqual(vm.available(), expected)
                    self.assertEqual(reads, expected_reads)
                    if not stop:
                        self.assertFalse(reads)


if __name__ == '__main__':
    unittest.main()
