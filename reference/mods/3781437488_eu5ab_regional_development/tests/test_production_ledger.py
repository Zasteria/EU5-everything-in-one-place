"""Regression examples for monthly production, not accumulated inventory."""
import unittest
from dataclasses import replace

from src.eu5autobuild.production_ledger import assess, net_output
from src.eu5autobuild.engine import (
    AutomationContext, BuildingCandidate, GoodsMarketState, MarketState,
    candidate_pending_factor,
)


class ProductionLedgerTests(unittest.TestCase):
    def test_net_replacement_is_per_good_and_never_negative(self):
        self.assertAlmostEqual(net_output({'tools': 2}, {'tools': 1.1})['tools'], .9)
        self.assertEqual(net_output({'tools': 1}, {'tools': 2}), {'tools': 0})
        self.assertEqual(net_output({'beer': 2}, {'tools': 1}), {'beer': 2})

    def test_joint_goods_weighting_and_any_full_output_veto(self):
        args = ({'tools': 1, 'beer': 2}, {'tools': 100, 'beer': 100},
                {'tools': 100, 'beer': 100}, {'tools': 5, 'beer': 0},
                {'tools': 10, 'beer': 5})
        self.assertEqual(assess(*args), .875)
        self.assertEqual(assess(*args[:3], {'tools': 10}, args[4]), 0)
        self.assertEqual(assess(*args[:3], {'tools': 10}, args[4], emergency=True), 1)

    def test_real_plus_future_demand_missing_data_and_zero_delta(self):
        self.assertGreater(assess({'tools': 1}, {'tools': 0}, {'tools': 0}, {'tools': 1}, {'tools': 1}, {'tools': 5}), 0)
        self.assertEqual(assess({'tools': 1}, {}, {}, {}, {'tools': 1}, emergency=True), 0)
        self.assertEqual(assess({'tools': 0}, {}, {}, {}, {}), 1)
        self.assertEqual(assess({'tools': float('nan')}, {}, {}, {}, {}), 0)

    def test_decision_model_consumes_explicit_net_flows_and_keeps_windmills_neutral(self):
        candidate = BuildingCandidate('workshop', ('tools',), 100, 1,
                                      net_monthly_outputs={'tools': 1}, output_base_prices={'tools': 2})
        context = AutomationContext(market=MarketState(goods={
            'tools': GoodsMarketState(100, 100, pending_output=5)}))
        self.assertEqual(candidate_pending_factor(candidate, context, None), .75)
        self.assertEqual(candidate_pending_factor(replace(candidate, production_identity_known=False), context, None), 1)
        self.assertEqual(candidate_pending_factor(replace(candidate, id='windmill'), context, None), 1)
        context = replace(context, market=MarketState(goods={
            'tools': GoodsMarketState(0, 0, pending_output=5, future_input=10)}))
        self.assertAlmostEqual(candidate_pending_factor(candidate, context, None), 1 - (5/11)**2)


if __name__ == '__main__':
    unittest.main()
