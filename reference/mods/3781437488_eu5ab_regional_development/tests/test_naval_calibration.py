"""Offline naval model calibration; live planner execution is tested separately."""
import unittest
from dataclasses import replace

from src.eu5autobuild.governor_model import (
    PropagationBudgetExceeded, evaluate_candidate, evaluate_migration_pair,
)
from tests.test_governor_model import _location


class NavalCalibrationTests(unittest.TestCase):
    def graph(self):
        nodes = {n: _location(n, proximity=100, is_port=True) for n in range(10)}
        neighbors = {n: {m for m in (n-1, n+1) if m in nodes} for n in nodes}
        roads = {frozenset((n, n+1)): "railroad" for n in range(9)}
        return nodes, neighbors, roads

    def test_naval_reaches_beyond_six_edges_and_rejects_partial_propagation(self):
        nodes, neighbors, roads = self.graph()
        nodes = {n: replace(v, proximity=0) for n, v in nodes.items()}
        result = evaluate_candidate(0, nodes, neighbors, roads, naval=True)
        self.assertEqual(result.covered_locations, 10)
        with self.assertRaises(PropagationBudgetExceeded):
            evaluate_candidate(0, nodes, neighbors, roads, naval=True, max_steps=1)

    def test_naval_pair_does_not_mix_live_proximity_with_model(self):
        nodes, neighbors, roads = self.graph()
        first = evaluate_migration_pair(0, 9, {0: 80}, nodes, neighbors, roads, naval=True)
        second = evaluate_migration_pair(0, 9, {0: 80},
            {n: replace(v, proximity=0) for n, v in nodes.items()}, neighbors, roads, naval=True)
        self.assertEqual(first.net_gain, second.net_gain)
        self.assertEqual(first.net_gain, 0)


if __name__ == "__main__":
    unittest.main()
