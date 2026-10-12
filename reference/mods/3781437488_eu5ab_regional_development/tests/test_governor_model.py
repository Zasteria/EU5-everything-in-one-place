import unittest
from dataclasses import replace
from decimal import Decimal

from src.eu5autobuild.governor_model import (
    LocationState,
    MigrationProposal,
    MigrationHysteresis,
    cheap_score,
    choose_migration,
    evaluate_candidate,
    evaluate_migration_pair,
    evaluate_naval_relocation_candidates,
    location_value,
    propagate_proximity,
    rank_local_candidates,
    rank_migration_pairs,
    rank_naval_components,
)


def _location(
    location_id: int,
    *,
    proximity: float,
    value_scale: float = 1.0,
    is_port: bool = False,
    control: float = 0.5,
    max_control: float = 1.0,
) -> LocationState:
    return LocationState(
        id=location_id,
        name=f"location_{location_id}",
        rank="city",
        proximity=proximity,
        control=control,
        max_control=max_control,
        population=10.0 * value_scale,
        potential_tax_base=5.0 * value_scale,
        development=15.0 * value_scale,
        road_to_capital=True,
        is_port=is_port,
    )


class GovernorModelTests(unittest.TestCase):
    def test_population_uses_save_units_and_profiles_have_distinct_priorities(self):
        populous = _location(1, proximity=20, value_scale=1)
        rich = LocationState(
            **{
                **{field: getattr(populous, field) for field in populous.__dataclass_fields__},
                "id": 2,
                "population": 2,
                "potential_tax_base": 20,
            }
        )
        populous = LocationState(
            **{
                **{field: getattr(populous, field) for field in populous.__dataclass_fields__},
                "population": 40,
                "potential_tax_base": 2,
            }
        )
        self.assertGreater(location_value(rich, "economic"), location_value(populous, "economic"))
        self.assertGreater(
            location_value(populous, "administrative_population"),
            location_value(rich, "administrative_population"),
        )

    def test_current_proximity_and_actual_road_quality_change_marginal_gain(self):
        locations = {
            1: _location(1, proximity=70),
            2: _location(2, proximity=45),
            3: _location(3, proximity=20),
        }
        neighbors = {1: {2}, 2: {1, 3}, 3: {2}}
        gravel = {frozenset((1, 2)): "gravel_road", frozenset((2, 3)): "gravel_road"}
        paved = {frozenset((1, 2)): "paved_road", frozenset((2, 3)): "paved_road"}
        no_roads = {}
        no_road_score = evaluate_candidate(1, locations, neighbors, no_roads)
        gravel_score = evaluate_candidate(1, locations, neighbors, gravel)
        paved_score = evaluate_candidate(1, locations, neighbors, paved)
        self.assertGreater(gravel_score.marginal_gain, no_road_score.marginal_gain)
        self.assertGreater(paved_score.marginal_gain, gravel_score.marginal_gain)
        self.assertEqual(no_road_score.site_gain, gravel_score.site_gain)
        self.assertEqual(gravel_score.site_gain, paved_score.site_gain)
        self.assertGreater(gravel_score.surrounding_gain, no_road_score.surrounding_gain)
        self.assertGreater(paved_score.surrounding_gain, gravel_score.surrounding_gain)

        covered = dict(locations)
        covered[2] = _location(2, proximity=65)
        covered[3] = _location(3, proximity=55)
        self.assertLess(
            evaluate_candidate(1, covered, neighbors, paved).marginal_gain,
            paved_score.marginal_gain,
        )

    def test_useless_extra_road_does_not_create_a_score_bonus(self):
        locations = {
            1: _location(1, proximity=20, control=0.2),
            2: _location(2, proximity=80, control=1.0),
        }
        neighbors = {1: {2}, 2: {1}}
        no_roads: dict[frozenset[int], str] = {}
        useless_road = {frozenset((1, 2)): "gravel_road"}

        without_road = evaluate_candidate(1, locations, neighbors, no_roads)
        with_road = evaluate_candidate(1, locations, neighbors, useless_road)

        self.assertEqual(without_road.score, with_road.score)
        self.assertEqual(without_road.site_gain, with_road.site_gain)
        self.assertEqual(without_road.surrounding_gain, with_road.surrounding_gain)
        self.assertEqual(
            cheap_score(1, locations, neighbors, no_roads),
            cheap_score(1, locations, neighbors, useless_road),
        )

    def test_score_is_exact_sum_of_site_and_surrounding_improvements(self):
        locations = {
            1: _location(1, proximity=25, control=0.7),
            2: _location(2, proximity=10, control=0.2, value_scale=2),
        }
        neighbors = {1: {2}, 2: {1}}
        roads = {frozenset((1, 2)): "paved_road"}

        result = evaluate_candidate(1, locations, neighbors, roads)

        self.assertGreater(result.site_gain, 0)
        self.assertGreater(result.surrounding_gain, 0)
        self.assertEqual(result.site_gain + result.surrounding_gain, result.marginal_gain)
        self.assertEqual(result.marginal_gain, result.score)
        self.assertEqual(
            Decimal(f"{result.score:.1f}"),
            Decimal(f"{result.site_gain:.1f}") + Decimal(f"{result.surrounding_gain:.1f}"),
        )

    def test_control_is_a_downstream_result_not_a_score_multiplier(self):
        high_control = {
            1: _location(1, proximity=10, control=0.9),
            2: _location(2, proximity=10, control=0.9, value_scale=3),
        }
        low_control_neighbor = dict(high_control)
        low_control_neighbor[2] = _location(
            2, proximity=10, control=0.1, value_scale=3
        )
        neighbors = {1: {2}, 2: {1}}
        roads = {frozenset((1, 2)): "paved_road"}

        high_area_score = evaluate_candidate(1, high_control, neighbors, roads)
        mixed_area_score = evaluate_candidate(1, low_control_neighbor, neighbors, roads)

        self.assertEqual(high_area_score.site_gain, mixed_area_score.site_gain)
        self.assertEqual(
            mixed_area_score.surrounding_gain,
            high_area_score.surrounding_gain,
        )
        self.assertEqual(mixed_area_score.score, high_area_score.score)
        self.assertEqual(mixed_area_score.marginal_gain, high_area_score.marginal_gain)

    def test_proximity_is_the_observable_control_input(self):
        locations = {
            1: _location(1, proximity=20, control=0.1),
            2: _location(2, proximity=20, control=0.1, value_scale=2),
        }
        neighbors = {1: {2}, 2: {1}}
        roads = {frozenset((1, 2)): "paved_road"}
        lower_proximity = evaluate_candidate(1, locations, neighbors, roads)
        locations[2] = _location(2, proximity=70, control=0.1, value_scale=2)
        higher_proximity = evaluate_candidate(1, locations, neighbors, roads)
        self.assertGreater(lower_proximity.surrounding_gain, higher_proximity.surrounding_gain)

    def test_existing_proximity_above_candidate_path_creates_no_gain(self):
        locations = {
            1: _location(1, proximity=20),
            2: _location(2, proximity=70, value_scale=10),
        }
        result = evaluate_candidate(
            1,
            locations,
            {1: {2}, 2: {1}},
            {frozenset((1, 2)): "paved_road"},
        )

        self.assertEqual(result.surrounding_gain, 0)
        self.assertEqual(result.covered_locations, 1)
        self.assertEqual([item.location_id for item in result.contributions], [1])

    def test_control_and_max_control_are_diagnostics_not_scoring_inputs(self):
        base = {
            1: _location(1, proximity=20, control=0.1, max_control=0.2),
            2: _location(2, proximity=10, control=0.2, max_control=0.3),
        }
        buffed = {
            1: replace(base[1], control=0.95, max_control=1.0),
            2: replace(base[2], control=0.9, max_control=0.95),
        }
        neighbors = {1: {2}, 2: {1}}
        roads = {frozenset((1, 2)): "paved_road"}

        base_result = evaluate_candidate(1, base, neighbors, roads)
        buffed_result = evaluate_candidate(1, buffed, neighbors, roads)

        self.assertEqual(base_result.score, buffed_result.score)
        self.assertEqual(base_result.site_gain, buffed_result.site_gain)
        self.assertEqual(base_result.surrounding_gain, buffed_result.surrounding_gain)
        self.assertEqual(base_result.contributions[0].old_control, 0.1)
        self.assertEqual(base_result.contributions[0].old_max_control, 0.2)
        self.assertIsNone(base_result.contributions[0].new_max_control)
        self.assertIsNone(base_result.contributions[0].max_control_gain)

    def test_runtime_edge_cache_replays_destination_scoped_road_cost(self):
        base_locations = {
            1: _location(1, proximity=20),
            2: _location(2, proximity=10, value_scale=4),
        }
        cached_locations = dict(base_locations)
        cached_locations[2] = replace(
            base_locations[2],
            edge_cost_factor=2.0,
            road_edge_base_cost=30.0,
            land_edge_base_cost=60.0,
        )
        neighbors = {1: {2}, 2: {1}}
        roads = {frozenset((1, 2)): "paved_road"}

        fallback_result = evaluate_candidate(1, base_locations, neighbors, roads)
        cached_result = evaluate_candidate(1, cached_locations, neighbors, roads)
        neighbor_contribution = next(
            item for item in cached_result.contributions if item.location_id == 2
        )

        # 30 - paved-road discount 5 * destination factor 2 = edge cost 20.
        self.assertEqual(neighbor_contribution.candidate_proximity, 60)
        self.assertLess(cached_result.surrounding_gain, fallback_result.surrounding_gain)

        railroad_result = evaluate_candidate(
            1,
            {
                1: base_locations[1],
                2: replace(
                    base_locations[2],
                    edge_cost_factor=0.5,
                    road_edge_base_cost=2.5,
                    land_edge_base_cost=20.0,
                ),
            },
            neighbors,
            {frozenset((1, 2)): "railroad"},
        )
        railroad_neighbor = next(
            item for item in railroad_result.contributions if item.location_id == 2
        )
        # The game clamps (road base 5 - railroad discount 15) to 0.01,
        # then applies the destination factor 0.5.
        self.assertAlmostEqual(railroad_neighbor.candidate_proximity, 79.995)

    def test_six_paved_edges_pay_real_cost_instead_of_the_floor_as_a_cap(self):
        locations = {
            location_id: replace(
                _location(location_id, proximity=0),
                edge_cost_factor=1.0,
                road_edge_base_cost=20.0,
                land_edge_base_cost=40.0,
            )
            for location_id in range(7)
        }
        neighbors = {
            location_id: {
                neighbor
                for neighbor in (location_id - 1, location_id + 1)
                if 0 <= neighbor <= 6
            }
            for location_id in range(7)
        }
        roads = {
            frozenset((location_id, location_id + 1)): "paved_road"
            for location_id in range(6)
        }

        propagated = propagate_proximity(
            {0: 80}, locations, neighbors, roads
        )

        self.assertEqual(
            [propagated[location_id] for location_id in range(7)],
            [80, 65, 50, 35, 20, 5, 0],
        )

    def test_counterfactual_relocation_removes_old_source_before_adding_new(self):
        locations = {
            1: _location(1, proximity=80, value_scale=1),
            2: _location(2, proximity=60, value_scale=1),
            3: _location(3, proximity=40, value_scale=4),
        }
        neighbors = {1: {2}, 2: {1, 3}, 3: {2}}
        roads = {
            frozenset((1, 2)): "gravel_road",
            frozenset((2, 3)): "gravel_road",
        }

        proposal = evaluate_migration_pair(
            1,
            3,
            {1: 80},
            locations,
            neighbors,
            roads,
        )

        by_location = {item.location_id: item for item in proposal.contributions}
        self.assertEqual(by_location[1].proximity_without_current, 0)
        self.assertEqual(by_location[1].replacement_proximity, 40)
        self.assertEqual(by_location[1].after_proximity, 40)
        self.assertGreater(proposal.recommended_score, proposal.current_score)
        self.assertEqual(
            proposal.net_gain,
            proposal.recommended_score - proposal.current_score,
        )

    def test_counterfactual_relocation_preserves_other_sources_and_handles_overlap(self):
        base_locations = {
            1: _location(1, proximity=0, value_scale=1),
            2: _location(2, proximity=0, value_scale=3),
            3: _location(3, proximity=0, value_scale=2),
            4: _location(4, proximity=0, value_scale=1),
        }
        neighbors = {1: {2}, 2: {1, 3}, 3: {2, 4}, 4: {3}}
        roads = {
            frozenset((1, 2)): "paved_road",
            frozenset((2, 3)): "paved_road",
            frozenset((3, 4)): "paved_road",
        }
        current_field = propagate_proximity(
            {1: 80, 4: 80}, base_locations, neighbors, roads
        )
        locations = {
            location_id: replace(
                location,
                proximity=current_field.get(location_id, 0),
            )
            for location_id, location in base_locations.items()
        }

        proposal = evaluate_migration_pair(
            1,
            2,
            {1: 80, 4: 80},
            locations,
            neighbors,
            roads,
        )

        by_location = {item.location_id: item for item in proposal.contributions}
        self.assertEqual(by_location[1].proximity_without_current, 35)
        self.assertNotIn(4, by_location)
        self.assertEqual(current_field[4], 80)
        self.assertEqual(proposal.covered_locations, len(proposal.contributions))

    def test_overlapping_sources_are_capped_only_when_propagated(self):
        locations = {
            1: _location(1, proximity=100),
            2: _location(2, proximity=80),
        }
        neighbors = {1: {2}, 2: {1}}
        roads = {frozenset((1, 2)): "gravel_road"}

        propagated = propagate_proximity(
            {1: 160}, locations, neighbors, roads
        )
        self.assertEqual(propagated[1], 100)
        self.assertEqual(propagated[2], 80)

        # Removing one 80-point Governor source from a 160-point raw stack
        # leaves the other source intact before the 0-100 propagation cap.
        proposal = evaluate_migration_pair(
            1,
            2,
            {1: 160},
            locations,
            neighbors,
            roads,
        )
        first = next(item for item in proposal.contributions if item.location_id == 1)
        self.assertEqual(first.proximity_without_current, 80)

    def test_pair_ranking_checks_every_existing_governor_and_destination(self):
        locations = {
            1: _location(1, proximity=80, value_scale=1),
            2: _location(2, proximity=60, value_scale=1),
            3: _location(3, proximity=60, value_scale=5),
            4: _location(4, proximity=80, value_scale=1),
        }
        neighbors = {1: {2}, 2: {1}, 3: {4}, 4: {3}}
        roads = {
            frozenset((1, 2)): "gravel_road",
            frozenset((3, 4)): "gravel_road",
        }

        proposals = rank_migration_pairs(
            {1, 4},
            (location_id for location_id in (2, 3)),
            {1: 80, 4: 80},
            locations,
            neighbors,
            roads,
        )

        self.assertEqual(len(proposals), 4)
        self.assertEqual(proposals[0].recommended_location_id, 3)
        self.assertIn(proposals[0].current_location_id, {1, 4})

    def test_runtime_value_is_authoritative_and_strategic_weight_is_applied_once(self):
        base = replace(
            _location(1, proximity=20, is_port=True),
            has_fort=True,
            is_border=True,
        )
        self.assertGreater(
            location_value(base, strategic_value=True),
            location_value(base, strategic_value=False),
        )
        cached = replace(base, runtime_value=123.456)
        self.assertEqual(location_value(cached, strategic_value=False), 123.456)
        self.assertEqual(location_value(cached, strategic_value=True), 123.456)

    def test_local_ranking_depends_only_on_final_network_state(self):
        locations = {
            1: _location(1, proximity=65),
            2: _location(2, proximity=35, value_scale=2),
            3: _location(3, proximity=10),
        }
        neighbors = {1: {2}, 2: {1, 3}, 3: {2}}
        roads = {frozenset((1, 2)): "paved_road", frozenset((2, 3)): "gravel_road"}
        manual = rank_local_candidates((1, 2, 3), locations, neighbors, roads)
        ogas = rank_local_candidates((1, 2, 3), locations, neighbors, dict(roads))
        other_mod = rank_local_candidates((1, 2, 3), locations, neighbors, roads.copy())
        self.assertEqual(manual, ogas)
        self.assertEqual(ogas, other_mod)

    def test_naval_ranking_retains_all_legal_ports_across_components(self):
        locations = {
            1: _location(1, proximity=20, is_port=True),
            2: _location(2, proximity=20),
            3: _location(3, proximity=20, value_scale=2, is_port=True),
            4: _location(4, proximity=10, is_port=True),
            5: _location(5, proximity=10),
        }
        neighbors = {1: {2}, 2: {1, 3}, 3: {2}, 4: {5}, 5: {4}}
        winners = rank_naval_components(
            ({1, 2, 3}, {4, 5}),
            {1, 3, 4},
            set(),
            locations,
            neighbors,
            {},
        )
        self.assertEqual(len(winners), 3)
        self.assertIn(winners[0].location_id, {1, 3})
        self.assertEqual({winner.location_id for winner in winners} & {1, 3}, {1, 3})
        self.assertIn(4, {winner.location_id for winner in winners})
        relocation_candidates = evaluate_naval_relocation_candidates(
            ({1, 2, 3}, {4, 5}),
            {1, 3, 4},
            locations,
            neighbors,
            {},
        )
        self.assertEqual(
            {candidate.location_id for candidate in relocation_candidates},
            {1, 3, 4},
        )

    def test_migration_requires_absolute_relative_persistence_confidence_and_cooldown(self):
        below_relative = MigrationProposal(10, 20, 10, 11.9, 1.9, 1)
        below_absolute = MigrationProposal(10, 30, 10, 12.1, 2.1, 1)
        eligible = MigrationProposal(10, 40, 10, 13, 3, 1)
        self.assertIsNone(
            choose_migration([below_relative], nationwide_value=100)
        )
        self.assertIsNone(
            choose_migration([below_absolute], nationwide_value=200)
        )
        proposal = choose_migration(
            [below_relative, below_absolute, eligible], nationwide_value=100
        )
        self.assertIsNotNone(proposal)
        tracker = MigrationHysteresis()
        self.assertFalse(tracker.observe(proposal))
        self.assertTrue(tracker.observe(proposal))
        self.assertFalse(tracker.observe(proposal))
        tracker.advance_months(12)
        self.assertFalse(tracker.observe(proposal))
        self.assertFalse(tracker.observe(proposal, confidence_sufficient=False))
        self.assertIsNone(tracker.accepted_pair)


if __name__ == "__main__":
    unittest.main()
