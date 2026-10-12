"""Targeted checks for changed-seat gates and competing layout proposals."""
import unittest
from dataclasses import replace
from functools import partial
from unittest.mock import patch

from src.eu5autobuild.governor_layout_policy import plan_complete_layout as _plan_complete_layout
from src.eu5autobuild.governor_layout_policy import capital_transport_costs
from src.eu5autobuild.governor_model import LocationState, propagate_proximity
from src.eu5autobuild.governor_transport import (
    CountryTransportInputs, LocationTransportInputs, TransportContext, TransportMode,
)

# Small numeric fixtures isolate comparison mechanics under explicit settings;
# the user-selected production defaults have independent tests below.
plan_complete_layout = partial(_plan_complete_layout, relative_rate=.1)


def locations(values):
    return {n: LocationState(n, str(n), "city", 0, .5, None, 10, 10, 10,
                             runtime_value=value)
            for n, value in enumerate(values)}


class MigrationPolicyTests(unittest.TestCase):
    def test_default_requires_eighty_percent_without_absolute_floor(self):
        for old, new, qualifies, threshold in (
            (1000, 1799, False, 640),
            (100, 400, True, 64),     # +240 is no longer blocked by 300.
            (1000, 1800, True, 640),  # The relative boundary is inclusive.
            (1, 1.8, True, .64),
        ):
            with self.subTest(old=old, new=new):
                result = _plan_complete_layout({1}, {2}, {0: 100, 1: 80},
                                               locations([10, old, new]), {}, {}, capital=0)
                self.assertEqual(result["relative_rate"], .8)
                self.assertEqual(result["qualifies"], qualifies)
                self.assertEqual(result["full_layout"]["migration_threshold"], threshold)

    def plan(self, values, existing, candidates, *, sources=None, **kwargs):
        if sources is None:
            sources = {0: 100, **{n: 80 for n in existing}}
        return plan_complete_layout(existing, candidates, sources,
                                    locations(values), {}, {}, capital=0, **kwargs)

    def test_failed_full_layout_cannot_hide_qualifying_single_swap(self):
        # A useful inner-band site is deliberately chosen by full planning
        # even though its low value makes the complete proposal worse.
        with patch("src.eu5autobuild.governor_layout_policy.capital_transport_costs",
                   return_value={0: 0, 1: 80, 2: 80, 3: 0, 4: 80}):
            result = self.plan([10, 100, 100, 10, 110], {1, 2}, {3, 4})
        self.assertLess(result["full_layout"]["modeled_net"], 0)
        self.assertFalse(result["full_layout"]["qualifies"])
        self.assertTrue(result["qualifies"])
        self.assertEqual(result["proposal_kind"], "single_swap")
        self.assertEqual({s["destination_id"] for s in result["steps"]}, {2, 4})
        self.assertEqual(result["modeled_net"], 8)
        self.assertEqual(result["changed_contribution"], 80)
        self.assertEqual(result["migration_threshold"], 8)
        self.assertEqual(result["single_swap_comparisons"], 4)
        self.assertEqual(result["footprint_propagations"], 4)

    def test_better_full_layout_wins_and_counts_all_changed_seats(self):
        result = self.plan([10, 100, 100, 200, 200], {1, 2}, {3, 4})
        self.assertEqual(result["proposal_kind"], "full_layout")
        self.assertEqual(result["modeled_net"], 160)
        self.assertEqual(result["changed_contribution"], 160)
        self.assertEqual(result["migration_threshold"], 16)
        self.assertEqual(result["relative_rate"], .1)

    def test_larger_net_ineligible_full_cannot_hide_smaller_eligible_single(self):
        nodes = locations([10, 1000, 10, 1200, 200])
        graph = {1: {3}, 3: {1}, 2: {4}, 4: {2}}
        roads = {frozenset((1, 3)): "railroad"}
        with patch("src.eu5autobuild.governor_layout_policy.capital_transport_costs",
                   return_value={0: 0, 1: 80, 2: 80, 3: 0, 4: 40}):
            result = plan_complete_layout({1, 2}, {3, 4}, {0: 100, 1: 80, 2: 80},
                                          nodes, graph, roads, capital=0)
        self.assertEqual(result["full_layout"]["modeled_net"], 86)
        self.assertFalse(result["full_layout"]["qualifies"])
        self.assertEqual(result["full_layout"]["migration_threshold"], 178.8)
        self.assertTrue(result["qualifies"])
        self.assertEqual(result["proposal_kind"], "single_swap")
        self.assertEqual(result["modeled_net"], 76)
        self.assertEqual(result["migration_threshold"], 8.8)
        self.assertEqual({s["destination_id"] for s in result["steps"]}, {1, 4})

    def test_all_negative_proposals_retain_original_layout(self):
        with patch("src.eu5autobuild.governor_layout_policy.capital_transport_costs",
                   return_value={0: 0, 1: 80, 2: 80, 3: 0, 4: 80}):
            result = self.plan([10, 100, 100, 10, 90], {1, 2}, {3, 4})
        self.assertEqual(result["proposal_kind"], "retain")
        self.assertFalse(result["qualifies"])
        self.assertEqual(result["modeled_net"], 0)
        self.assertEqual(result["modeled_before"], result["modeled_after"])
        self.assertTrue(all(s["retained"] for s in result["steps"]))
        self.assertLess(result["full_layout"]["modeled_net"], 0)

    def test_unrelated_wealth_cannot_raise_migration_threshold(self):
        original = self.plan([10, 100, 120], {1}, {2})
        enlarged = self.plan([10, 100, 120, 1_000_000], {1}, {2},
                             sources={0: 100, 1: 80, 3: 100})
        for result in (original, enlarged):
            self.assertTrue(result["qualifies"])
            self.assertEqual(result["modeled_net"], 16)
            self.assertEqual(result["migration_threshold"], 8)

    def test_source_overlap_survives_removing_the_governor(self):
        # Keep the old site's independent 20-point source. The new site's
        # existing 40-point source means adding 80 is capped at 100.
        result = self.plan([10, 100, 200], {1}, {2}, sources={0: 100, 1: 100, 2: 40})
        self.assertEqual(result["modeled_before"], 80)
        self.assertEqual(result["changed_contribution"], 80)
        self.assertEqual(result["modeled_after"], 120)
        self.assertEqual(result["modeled_net"], 40)

    def test_multi_seat_shared_coverage_uses_joint_retained_baseline(self):
        nodes = locations([10, 100, 100, 300, 300])
        graph = {1: {2}, 2: {1}}
        roads = {frozenset((1, 2)): "railroad"}
        result = plan_complete_layout({1, 2}, {3, 4}, {0: 100, 1: 80, 2: 80},
                                      nodes, graph, roads, capital=0)
        # Removing either old seat alone loses only five points. Removing
        # both loses 160: summing individual exclusive contributions is wrong.
        self.assertEqual(result["proposal_kind"], "full_layout")
        self.assertEqual(result["changed_contribution"], 160)
        self.assertEqual(result["migration_threshold"], 16)

    def test_small_positive_gain_has_no_fixed_floor(self):
        result = self.plan([10, .1, 2], {1}, {2})
        self.assertGreater(result["full_layout"]["modeled_net"], 0)
        self.assertLess(result["full_layout"]["modeled_net"], 2)
        self.assertTrue(result["qualifies"])
        self.assertGreater(result["modeled_net"], 0)

    def test_nearly_zero_changed_contribution_uses_only_relative_threshold(self):
        result = self.plan([10, .01, 3], {1}, {2})
        self.assertTrue(result["qualifies"])
        self.assertAlmostEqual(result["changed_contribution"], .008)
        self.assertEqual(result["migration_threshold"], .001)

    def test_current_and_alternative_use_same_road_graph_not_live_proximity(self):
        nodes = locations([10, 100, 200, 100])
        graph = {0: {1}, 1: {0, 2}, 2: {1, 3}, 3: {2}}
        roads = {frozenset((n, n+1)): "railroad" for n in range(3)}
        result = plan_complete_layout({1}, {3}, {0: 100, 1: 80},
                                      nodes, graph, roads, capital=0)
        changed_live = {n: replace(node, proximity=100-n*20) for n, node in nodes.items()}
        other = plan_complete_layout({1}, {3}, {0: 100, 1: 80},
                                     changed_live, graph, roads, capital=0)
        self.assertEqual(result["modeled_before"], 0)
        self.assertEqual(result["modeled_net"], other["modeled_net"])
        self.assertEqual(result["steps"], other["steps"])
        self.assertNotEqual(result["live_model_absolute_weighted_error"],
                            other["live_model_absolute_weighted_error"])
        # An independent propagation confirms the capital already covers all
        # nodes better than the old or prospective seat on this same graph.
        base = propagate_proximity({0: 100}, nodes, graph, roads, max_depth=None)
        new = propagate_proximity({0: 100, 3: 80}, nodes, graph, roads, max_depth=None)
        self.assertEqual(base, new)

    def test_no_seats_is_a_valid_empty_retention(self):
        result = self.plan([10, 100], set(), {1})
        self.assertFalse(result["qualifies"])
        self.assertEqual(result["steps"], [])
        self.assertEqual(result["single_swap_comparisons"], 0)

    def test_invalid_gate_configuration_rejected(self):
        for kwargs in ({"relative_rate": -1}, {"relative_rate": float("nan")},
                       {"relative_rate": float("inf")}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.plan([10, 100, 120], {1}, {2}, **kwargs)

    def test_calibrated_capital_distances_use_source_inputs(self):
        nodes = locations([10, 10, 10])
        graph = {0: {1}, 1: {0, 2}, 2: {1}}
        edges = frozenset({frozenset((0, 1)), frozenset((1, 2))})
        ctx = TransportContext(CountryTransportInputs(0, 0, 0),
                               {n: LocationTransportInputs(1 if n == 0 else 0, 0, 0) for n in nodes},
                               edges, mode=TransportMode.HIGHEST_UNLOCKED,
                               unlocked_advances=frozenset({"railroad_advance"}),
                               buildable_land_edges=edges)
        self.assertEqual(capital_transport_costs(0, nodes, graph, {}, transport_context=ctx),
                         {0: 0, 1: 2.5, 2: 7.5})
        result = plan_complete_layout({1}, {2}, {0: 100, 1: 80},
                                      nodes, graph, {}, capital=0, transport_context=ctx)
        self.assertEqual(result["modeled_before"], 0)
        self.assertEqual(result["modeled_net"], 0)
        self.assertIsNone(result["live_model_absolute_weighted_error"])
        self.assertFalse(result["live_error_comparable"])
        actual = replace(ctx, mode=TransportMode.ACTUAL)
        result = plan_complete_layout({1}, {2}, {0: 100, 1: 80},
                                      nodes, graph, {}, capital=0, transport_context=actual)
        self.assertIsNotNone(result["live_model_absolute_weighted_error"])

    def test_lake_transit_not_in_economic_weights(self):
        nodes = locations([100, 100, 200, 1_000_000])
        nodes[3] = replace(nodes[3], is_transit_only=True)
        graph = {0: {3}, 3: {0, 1}, 1: {3}, 2: set()}
        ctx = TransportContext(CountryTransportInputs(0, 0, 0),
                               {n: LocationTransportInputs(0, 0, 0) for n in (0, 1, 2)},
                               frozenset(), non_land_edge_costs={(0, 3): 4, (3, 0): 4, (3, 1): 4, (1, 3): 4})
        result = plan_complete_layout({1}, {2}, {0: 100, 1: 80},
                                      nodes, graph, {}, capital=0, transport_context=ctx,
                                      scored_location_ids={0, 1, 2})
        self.assertEqual(result["modeled_before"], 0)
        self.assertEqual(result["modeled_net"], 160)
        self.assertEqual(result["minimum_site_gain"], 4)


if __name__ == "__main__":
    unittest.main()
