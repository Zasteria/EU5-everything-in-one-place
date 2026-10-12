import unittest
from copy import deepcopy
from dataclasses import replace
from functools import partial

from src.eu5autobuild.governor_model import LocationState, PropagationBudgetExceeded
from src.eu5autobuild.governor_layout_policy import (
    LayoutConfirmation, capital_transport_costs, plan_complete_layout as _plan_complete_layout,
)

# These selection/propagation fixtures use the earlier sensitivity settings;
# the production defaults are verified separately in migration-policy tests.
plan_complete_layout = partial(_plan_complete_layout, relative_rate=.1)


def locations(count):
    return {n: LocationState(n, str(n), "city", 0, .5, None, 10, 10, 10)
            for n in range(count)}


class LayoutPolicyTests(unittest.TestCase):
    def test_capital_propagation_beyond_six_edges(self):
        nodes = locations(12)
        graph = {n: {m for m in (n-1, n+1) if m in nodes} for n in nodes}
        roads = {frozenset((n, n+1)): "railroad" for n in range(11)}
        distances = capital_transport_costs(0, nodes, graph, roads)
        self.assertEqual(distances[11], 55)
        result = plan_complete_layout({1}, range(1, 12), {0: 100, 1: 80},
                                      nodes, graph, roads, capital=0)
        self.assertGreater(result["steps"][0]["destination_id"], 6)
        self.assertEqual(result["modeled_before"], 0)
        self.assertGreater(result["modeled_after"], 0)

    def test_inner_band_precedes_a_more_valuable_outer_band(self):
        nodes = locations(5)
        nodes[1] = replace(nodes[1], runtime_value=1000)
        nodes[4] = replace(nodes[4], runtime_value=10000)
        graph = {0: {1}, 1: {0, 2}, 2: {1, 3}, 3: {2, 4}, 4: {3}}
        result = plan_complete_layout({4}, {1, 4}, {0: 100, 4: 80},
                                      nodes, graph, {}, capital=0)
        self.assertEqual(result["full_layout"]["steps"][0]["destination_id"], 1)
        # Inner-first is an explicit constraint, not a global-optimality claim.
        self.assertFalse(result["qualifies"])
        self.assertEqual(result["proposal_kind"], "retain")
        self.assertEqual(result["display_steps"][0]["destination_id"], 4)

    def test_all_old_sites_retained_and_more_than_three_rows(self):
        nodes = locations(6)
        result = plan_complete_layout({1, 2, 3, 4, 5}, set(),
                                      {0: 100, **{n: 80 for n in range(1, 6)}},
                                      nodes, {}, {}, capital=0)
        self.assertEqual(len(result["display_steps"]), 5)
        self.assertTrue(all(s["retained"] for s in result["display_steps"]))
        self.assertEqual(result["modeled_net"], 0)
        self.assertEqual(result["footprint_propagations"], 5)

    def test_retained_matching_reserves_all_old_destinations_first(self):
        nodes = locations(7)
        nodes[1] = replace(nodes[1], runtime_value=1000)
        nodes[2] = replace(nodes[2], runtime_value=1000)
        nodes[5] = replace(nodes[5], runtime_value=2000)
        nodes[6] = replace(nodes[6], runtime_value=2000)
        result = plan_complete_layout({1, 2, 3, 4}, {5, 6},
                                      {0: 100, 1: 80, 2: 80, 3: 80, 4: 80},
                                      nodes, {}, {}, capital=0)
        steps = result["steps"]
        self.assertEqual({s["origin_id"] for s in steps}, {1, 2, 3, 4})
        self.assertEqual({s["destination_id"] for s in steps}, {1, 2, 5, 6})
        self.assertTrue(all(s["origin_id"] == s["destination_id"]
                            for s in steps if s["destination_id"] in {1, 2}))

    def test_source_map_and_live_proximity_never_mutated(self):
        nodes = locations(3)
        sources = {0: 100, 1: 100}
        original = deepcopy((nodes, sources))
        plan_complete_layout({1}, {2}, sources, nodes, {}, {}, capital=0)
        self.assertEqual((nodes, sources), original)

    def test_incomplete_work_is_not_a_plan(self):
        with self.assertRaises(PropagationBudgetExceeded):
            plan_complete_layout({1}, {2}, {0: 100, 1: 80}, locations(3), {}, {},
                                 capital=0, max_steps=0)
        with self.assertRaises(PropagationBudgetExceeded):
            capital_transport_costs(0, locations(2), {0: {1}}, {}, max_steps=1)

    def test_all_candidates_evaluated_including_low_live_demand(self):
        nodes = locations(15)
        nodes[14] = replace(nodes[14], proximity=100, runtime_value=10000)
        result = plan_complete_layout({1}, range(2, 15), {0: 100, 1: 80},
                                      nodes, {}, {}, capital=0)
        self.assertEqual(result["steps"][0]["destination_id"], 14)
        self.assertEqual(result["footprint_propagations"], 14)

    def test_whole_set_confirmation_and_cooldown(self):
        plan = dict(qualifies=True, existing=[dict(id=n) for n in (1, 2, 3, 4)],
                    steps=[dict(destination_id=n) for n in (5, 6, 7, 8)])
        state = LayoutConfirmation()
        self.assertFalse(state.observe(plan))
        plan["steps"][-1]["destination_id"] = 9
        self.assertFalse(state.observe(plan))  # fourth row matters
        plan["steps"].reverse()
        self.assertTrue(state.observe(plan))   # order doesn't matter
        self.assertFalse(state.observe(plan))
        plan["steps"][0]["destination_id"] = 10
        self.assertFalse(state.observe(plan))
        self.assertFalse(state.observe(plan))  # cooldown survives target change
        for _ in range(12):
            state.month_elapsed()
        self.assertTrue(state.observe(plan))
        self.assertFalse(state.observe(plan, valid=False))
        self.assertEqual(state.streak, 0)


if __name__ == "__main__":
    unittest.main()
