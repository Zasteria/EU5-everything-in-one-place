import tempfile
import unittest
from pathlib import Path

from scripts.validate_governor_save import parse_save
from src.eu5autobuild.governor_tax import estimate_monthly_tax_gain, parse_tax_rate_override


class GovernorTaxTests(unittest.TestCase):
    def test_confirmed_zero_tax_rates_are_explicit_and_validated(self):
        self.assertEqual(parse_tax_rate_override("clergy_estate=0"), ("clergy_estate", 0))
        for text in ("clergy_estate=nan", "clergy_estate=1.1", "clergy_estate=-1", "clergy=0"):
            with self.assertRaises(ValueError):
                parse_tax_rate_override(text)
        result = self.estimate(wealth={"nobles_estate": 100, "clergy_estate": 200},
                               rates={"nobles_estate": 0.2, "clergy_estate": 0})
        self.assertAlmostEqual(result["monthly_tax_gain"], 3)

    def estimate(self, ceiling=0.4, gain=20, wealth=None, rates=None):
        return estimate_monthly_tax_gain(
            ceiling, gain,
            {"nobles_estate": 100, "peasants_estate": 200} if wealth is None else wealth,
            {"nobles_estate": 0.2, "peasants_estate": 0.5} if rates is None else rates,
            control_per_full_proximity=0.75,
        )

    def test_wealth_is_weighted_by_actual_estate_rates(self):
        # 20 points of Proximity add 15 points of ceiling: (100*.2+200*.5)*.15.
        result = self.estimate()
        self.assertAlmostEqual(result["monthly_tax_gain"], 18)
        self.assertAlmostEqual(result["new_max_control"], 0.55)

    def test_control_ceiling_limits_income_and_existing_recovery_is_not_credited(self):
        self.assertAlmostEqual(self.estimate(ceiling=0.95)["monthly_tax_gain"], 6)
        # Even with low actual control, a location whose ceiling is already 100%
        # has no additional steady-state tax to attribute to a Governor.
        self.assertEqual(self.estimate(ceiling=1)["monthly_tax_gain"], 0)
        self.assertEqual(self.estimate(gain=0)["monthly_tax_gain"], 0)

    def test_missing_inputs_are_not_zero_income_or_guessed_tax_rates(self):
        for result in (self.estimate(ceiling=None), self.estimate(ceiling=0),
                       self.estimate(wealth={}), self.estimate(rates={"nobles_estate": 0.2})):
            self.assertIsNone(result["monthly_tax_gain"])
            self.assertTrue(result["reason"])
        self.assertEqual(self.estimate(rates={"nobles_estate": 0, "peasants_estate": 0})["monthly_tax_gain"], 0)

    def test_invalid_inputs_are_unavailable(self):
        for result in (self.estimate(gain=float("nan")), self.estimate(ceiling=1.1),
                       self.estimate(wealth={"nobles_estate": -1}),
                       self.estimate(rates={"nobles_estate": 2})):
            self.assertIsNone(result["monthly_tax_gain"])

    def test_missing_rate_interval_retains_known_tax_and_never_claims_a_point_estimate(self):
        result = self.estimate(rates={"nobles_estate": 0.2})
        self.assertIsNone(result["monthly_tax_gain"])
        self.assertAlmostEqual(result["monthly_tax_gain_lower"], 3)
        self.assertAlmostEqual(result["monthly_tax_gain_upper"], 33)

    def test_save_reader_keeps_country_rates_and_location_estate_wealth_separate(self):
        text = '''previous_played={ {
\tidtype=764
} }
countries={
764={
\tcapital=1
\teconomy={
\t\ttax_rates={
\t\t\tnobles_estate=0.2
\t\t\tpeasants_estate=0.5
\t\t}
\t}
}
765={
\teconomy={
\t\ttax_rates={
\t\t\tnobles_estate=0.9
\t\t}
\t}
}
market_manager={
locations={
\t\t1={
\t\t\towner=764
\t\t\tcontrol=0.1
\t\t\testate_tax={
\t\t\t\tnobles_estate=10
\t\t\t}
\t\t\testate_possible_tax={
\t\t\t\tnobles_estate=100
\t\t\t\tpeasants_estate=200
\t\t\t}
\t\t}
\t\t2={
\t\t\towner=764
\t\t}
disease_outbreak_manager={
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tax.eu5"
            path.write_text(text, encoding="utf-8")
            snapshot = parse_save(path)
        self.assertEqual(snapshot.tax_rates[764], {"nobles_estate": 0.2, "peasants_estate": 0.5})
        self.assertEqual(snapshot.tax_rates[765], {"nobles_estate": 0.9})
        self.assertEqual(snapshot.locations[1].estate_possible_tax, {"nobles_estate": 100, "peasants_estate": 200})
        self.assertEqual(snapshot.locations[2].estate_possible_tax, {})
