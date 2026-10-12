import unittest

from src.eu5autobuild.governor_layout import plan_layout
from src.eu5autobuild.governor_model import LocationState


class WholeLayoutTests(unittest.TestCase):
    def test_all_seats_are_replanned_and_retention_is_allowed(self):
        locations = {n: LocationState(n, str(n), "city", 80, .5, None, 10, 10, 10)
                     for n in range(5)}
        result = plan_layout({1, 2, 3, 4}, set(),
                             {0: 100, 1: 80, 2: 80, 3: 80, 4: 80},
                             locations, {}, {}, capital=0)
        self.assertEqual(result["rounds"], 4)
        self.assertEqual(len(result["retained"]), 4)
        self.assertEqual(result["modeled_net"], 0)
        self.assertEqual(result["footprint_propagations"], 4)

    def test_road_upgrade_can_move_seat_outwards_without_mutating_snapshot(self):
        locations = {n: LocationState(n, str(n), "city", 80, .5, None, 10, 10, 10)
                     for n in range(7)}
        neighbors = {n: {m for m in (n-1, n+1) if m in locations} for n in locations}
        roads = {frozenset((n, n+1)): "railroad" for n in range(6)}
        sources = {0: 100, 1: 80}
        result = plan_layout({1}, set(range(1, 7)), sources, locations,
                             neighbors, roads, capital=0, shortlist=None, max_depth=7)
        self.assertGreater(result["steps"][0]["destination_id"], 1)
        self.assertGreater(result["modeled_net"], 0)
        self.assertEqual(sources, {0: 100, 1: 80})
        self.assertTrue(all(v.proximity == 80 for v in locations.values()))

    def test_selected_footprints_reduce_subsequent_marginal_gain(self):
        locations = {n: LocationState(n, str(n), "city", 0, .5, None, 10, 10, 10)
                     for n in range(4)}
        neighbors = {0: {1}, 1: {0}, 2: {3}, 3: {2}}
        result = plan_layout({0, 1}, {0, 1, 2, 3}, {0: 80, 1: 80},
                             locations, neighbors, {}, capital=None, shortlist=None)
        destinations = {s["destination_id"] for s in result["steps"]}
        self.assertEqual(len(destinations & {0, 1}), 1)
        self.assertEqual(len(destinations & {2, 3}), 1)


if __name__ == "__main__":
    unittest.main()
