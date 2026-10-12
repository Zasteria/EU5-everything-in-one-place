"""Cached and uncached score pipelines must match at fixed-point boundaries."""
from collections import Counter
import unittest

from src.eu5autobuild.recipe_snapshot import SCORE_VALUES, FILTER_SCORE_VALUES, field
from tests.test_output_prices_runtime import PriceVM


class CountingScoreVM(PriceVM):
    def __init__(self):
        self.reads = Counter()
        super().__init__()

    def value(self, expression):
        if isinstance(expression, str) and expression.endswith('_live'):
            self.reads[expression] += 1
        return super().value(expression)


class CandidateScoreSnapshotTests(unittest.TestCase):
    def test_signed_scores_rounding_and_zero_factors_match_without_recomputation(self):
        vm = CountingScoreVM()
        for score, labor, price, pending, capacity in (
            (100, 1, 1, 1, 1), (-100, .4, .5, .2, .8),
            (0, 1, 0, 1, 1), (1, .00001, .00001, .00001, 1),
            (-1000000000000, .00001, .00001, .00001, .00001),
        ):
            with self.subTest(score=score, labor=labor):
                vm.clear()
                vm.native_values.update({
                    'eu5ab_candidate_base_score_live': score,
                    'eu5ab_candidate_current_labor_factor_live': labor,
                    'eu5ab_output_price_factor_live': price,
                    'eu5ab_candidate_pending_factor_live': pending,
                    'eu5ab_candidate_pending_preliminary_factor_live': pending,
                    'eu5ab_candidate_capacity_factor_live': capacity,
                })
                expected = vm.value('eu5ab_current_candidate_score')
                vm.reads.clear()
                vm.selections.clear()
                vm.execute(vm.effects['eu5ab_prepare_recipe_screen_snapshot'])
                self.assertNotIn(field('need_score') + '_ready', vm.variables)
                self.assertNotIn(field('input_cost') + '_ready', vm.variables)
                vm.execute(vm.effects['eu5ab_prepare_candidate_filter_prices'])
                selected = vm.selections.copy()
                for value in FILTER_SCORE_VALUES:
                    self.assertEqual(vm.reads[value + '_live'], 1, value)
                vm.execute(vm.effects['eu5ab_prepare_candidate_score_snapshot'])
                self.assertEqual(vm.selections, selected)
                for _ in range(4):
                    self.assertEqual(vm.value('eu5ab_current_candidate_score'), expected)
                for value in SCORE_VALUES:
                    self.assertEqual(vm.reads[value + '_live'], 1, value)
                vm.clear()
                vm.native_values['eu5ab_candidate_base_score_live'] = 123
                self.assertEqual(vm.value('eu5ab_candidate_base_score'), 123)
                self.assertEqual(vm.reads['eu5ab_candidate_base_score_live'], 2)


if __name__ == '__main__':
    unittest.main()
