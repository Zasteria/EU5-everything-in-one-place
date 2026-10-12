"""Transport evidence and road-planning invariants, independent of old caches."""

from dataclasses import replace
import math
import unittest

from src.eu5autobuild.governor_model import (
    LocationState,
    evaluate_candidate,
    evaluate_migration_pair,
    location_value,
    propagate_proximity,
    rank_local_candidates,
)
from src.eu5autobuild.governor_transport import (
    CountryTransportInputs,
    LocationTransportInputs,
    TransportContext,
    TransportInputError,
    TransportMode,
    highest_unlocked_road,
    lake_edge_cost,
    land_edge_cost,
)


def edge(a: int, b: int) -> frozenset[int]:
    return frozenset((a, b))


def location(location_id: int, *, proximity: float = 0.0) -> LocationState:
    return LocationState(
        id=location_id, name=f"location_{location_id}", rank="city",
        proximity=proximity, control=0, max_control=0,
        population=0, potential_tax_base=0, development=0,
        runtime_value=100,
        # Deliberately incompatible historical cache. New context must ignore it.
        edge_cost_factor=9, road_edge_base_cost=180, land_edge_base_cost=360,
    )


ZERO_COUNTRY = CountryTransportInputs(0, 0, 0)
PLAIN = LocationTransportInputs(0, 0, 0)


def context(*, mode: TransportMode = TransportMode.ACTUAL, advances=(), buildable=None):
    links = frozenset((edge(1, 2), edge(2, 3)))
    return TransportContext(
        country=ZERO_COUNTRY,
        locations={1: PLAIN, 2: PLAIN, 3: PLAIN},
        land_edges=links,
        mode=mode,
        unlocked_advances=frozenset(advances),
        buildable_land_edges=links if buildable is None else frozenset(buildable),
    )


class GovernorTransportTests(unittest.TestCase):
    def test_screen_rail_costs_use_source_speed_and_separate_hill_factor(self):
        # Actual engine screenshots: speed headings exclude the separate hill
        # penalty. Values are rounded UI inputs, so this checks a small interval
        # instead of claiming exact engine fixed-point agreement.
        observations = (
            ("Hangzhou -> Yuhang", 1.2186, 0, 2.25),
            ("Yuhang -> Linan", 0.8719, 0, 2.67),
            ("Linan -> Shexian", 0.8296, -0.25, 3.64),
            ("Shexian -> Xiuning", 0.9161, -0.25, 3.47),
            ("Fuliang -> Poyang", 0.9188, -0.25, 3.47),
        )
        for name, speed, topography, displayed in observations:
            with self.subTest(edge=name):
                actual = land_edge_cost(
                    LocationTransportInputs(speed, topography, -0.5),
                    ZERO_COUNTRY, "railroad",
                )
                self.assertAlmostEqual(actual, displayed, delta=0.011)

    def test_terrain_speed_are_not_added_into_one_denominator(self):
        source = LocationTransportInputs(1.0, -0.25, -0.2)
        self.assertAlmostEqual(land_edge_cost(source, ZERO_COUNTRY, "railroad"), 5 / 0.75 / 2)
        self.assertNotAlmostEqual(land_edge_cost(source, ZERO_COUNTRY, "railroad"), 5 / (1 + 1 - 0.25 - 0.2))
        self.assertAlmostEqual(land_edge_cost(source, ZERO_COUNTRY, None), 40 / 0.55 / 2)

    def test_terrain_modifier_positive_topography_and_separate_clamps(self):
        country = CountryTransportInputs(-3, 0, 1)
        source = LocationTransportInputs(0, -0.4, -0.5)
        self.assertAlmostEqual(land_edge_cost(source, country, "railroad"), 5 / 0.5 / 0.05)
        self.assertAlmostEqual(land_edge_cost(source, country, None), 40 / 0.5 / 0.05)
        self.assertEqual(land_edge_cost(LocationTransportInputs(0, 0.5, 0), ZERO_COUNTRY, "railroad"), 5)

    def test_source_topography_selects_its_own_country_impact(self):
        # A hills modifier must not silently be reused for a mountain edge.
        hills = LocationTransportInputs(0, -0.25, 0, topography_modifier=0.2)
        mountains = LocationTransportInputs(0, -0.5, 0, topography_modifier=-0.4)
        unrelated_fallback = CountryTransportInputs(0, 0, 99)
        self.assertAlmostEqual(land_edge_cost(hills, unrelated_fallback, "railroad"), 5 / 0.7)
        self.assertAlmostEqual(land_edge_cost(mountains, unrelated_fallback, "railroad"), 5 / 0.7)

    def test_calibrated_propagation_is_asymmetric_and_ignores_old_cache(self):
        transport = TransportContext(
            country=ZERO_COUNTRY,
            locations={1: LocationTransportInputs(1, 0, 0), 2: PLAIN},
            land_edges=frozenset((edge(1, 2),)),
        )
        locations = {1: location(1), 2: location(2)}
        graph = {1: {2}, 2: {1}}
        roads = {edge(1, 2): "railroad"}
        forward = propagate_proximity({1: 100}, locations, graph, roads, transport_context=transport)
        reverse = propagate_proximity({2: 100}, locations, graph, roads, transport_context=transport)
        self.assertEqual(forward[2], 97.5)
        self.assertEqual(reverse[1], 95)
        self.assertEqual(propagate_proximity({1: 100}, locations, graph, roads)[2], 55)

    def test_missing_new_inputs_cannot_fall_back_to_historical_factor(self):
        transport = replace(context(), locations={})
        with self.assertRaisesRegex(TransportInputError, "Missing source"):
            propagate_proximity({1: 100}, {1: location(1), 2: location(2)}, {1: {2}}, {}, transport_context=transport)

    def test_unlock_resolution_never_uses_world_road_or_age(self):
        self.assertIsNone(highest_unlocked_road({"age_6_revolutions", "railroad"}))
        for advance, road in (
            ("road_building", "gravel_road"),
            ("paved_road_advance", "paved_road"),
            ("modern_road_advance", "modern_road"),
            ("railroad_advance", "railroad"),
        ):
            self.assertEqual(highest_unlocked_road({advance}), road)
        self.assertEqual(highest_unlocked_road({"road_building", "railroad_advance"}), "railroad")

    def test_highest_road_covers_buildable_roadless_links_in_both_directions(self):
        transport = context(mode=TransportMode.HIGHEST_UNLOCKED, advances={"railroad_advance"})
        self.assertEqual(transport.edge_cost(1, 2, None), 5)
        self.assertEqual(transport.edge_cost(2, 1, "gravel_road"), 5)
        self.assertEqual(transport.edge_cost(2, 3, "paved_road"), 5)
        self.assertEqual(replace(transport, mode=TransportMode.ACTUAL).edge_cost(1, 2, None), 40)

    def test_no_unlock_keeps_existing_usable_roads_and_does_not_invent_gravel(self):
        transport = context(mode=TransportMode.HIGHEST_UNLOCKED)
        self.assertIsNone(transport.planned_road_type)
        self.assertEqual(transport.edge_cost(1, 2, None), 40)
        self.assertEqual(transport.edge_cost(2, 3, "railroad"), 5)

    def test_non_buildable_land_is_not_upgraded(self):
        transport = context(mode=TransportMode.HIGHEST_UNLOCKED, advances={"railroad_advance"}, buildable={edge(1, 2)})
        self.assertEqual(transport.edge_cost(1, 2, None), 5)
        self.assertEqual(transport.edge_cost(2, 3, None), 40)
        self.assertEqual(transport.edge_cost(2, 3, "paved_road"), 15)

    def test_lake_costs_require_independent_directional_evidence(self):
        transport = TransportContext(
            country=ZERO_COUNTRY, locations={1: PLAIN, 2: PLAIN},
            land_edges=frozenset(), mode=TransportMode.HIGHEST_UNLOCKED,
            unlocked_advances=frozenset(("railroad_advance",)),
            non_land_edge_costs={(1, 2): 2.2, (2, 1): 2.6},
        )
        self.assertEqual(transport.edge_cost(1, 2, None), 2.2)
        self.assertEqual(transport.edge_cost(2, 1, None), 2.6)
        with self.assertRaises(TransportInputError):
            replace(transport, non_land_edge_costs={(1, 2): 2.2}).edge_cost(2, 1, None)
        with self.assertRaises(TransportInputError):
            replace(transport, buildable_land_edges=frozenset((edge(1, 2),)))

    def test_observed_lake_cost_has_global_and_source_local_but_no_land_modifiers(self):
        country = CountryTransportInputs(0.536, 0.1224, 0.3)
        # Lake -> Nanchang: zero lake-local modifier, +53.6% global.
        self.assertAlmostEqual(lake_edge_cost(0, country), 2.60, delta=0.01)
        # Poyang -> lake: source development and bridge supply +27.65%.
        self.assertAlmostEqual(lake_edge_cost(0.2765, country), 2.20, delta=0.01)
        self.assertEqual(lake_edge_cost(0, country), lake_edge_cost(0, replace(country, land_speed=99, terrain_modifier=99)))

    def test_lake_transit_node_is_neither_scored_nor_counted_as_covered_land(self):
        locations = {1: location(1), 2: replace(location(2), is_transit_only=True), 3: location(3)}
        transport = TransportContext(
            country=ZERO_COUNTRY, locations={node: PLAIN for node in locations},
            land_edges=frozenset(), non_land_edge_costs={(1, 2): 4, (2, 1): 4, (2, 3): 4, (3, 2): 4},
        )
        graph = {1: {2}, 2: {1, 3}, 3: {2}}
        result = evaluate_candidate(1, locations, graph, {}, transport_context=transport)
        self.assertEqual(location_value(locations[2]), 0)
        self.assertEqual(result.score, 152)
        self.assertEqual(result.covered_locations, 2)
        self.assertEqual({item.location_id for item in result.contributions}, {1, 3})
        with self.assertRaisesRegex(ValueError, "transit-only"):
            evaluate_candidate(2, locations, graph, {}, transport_context=transport)

    def test_unclassified_edges_are_errors_not_guessed_land(self):
        with self.assertRaisesRegex(TransportInputError, "No verified"):
            context().edge_cost(1, 3, None)
        with self.assertRaises(TransportInputError):
            replace(context(), non_land_edge_costs={(1, 2): 4})

    def test_inputs_are_finite_and_context_copies_mutable_collections(self):
        for value in (math.inf, -math.inf, math.nan):
            with self.assertRaises(TransportInputError):
                LocationTransportInputs(value, 0, 0)
            with self.assertRaises(TransportInputError):
                replace(context(), non_land_edge_costs={(1, 3): value})
        inputs = {1: PLAIN, 2: PLAIN}
        transport = TransportContext(ZERO_COUNTRY, inputs, frozenset((edge(1, 2),)))
        inputs[1] = LocationTransportInputs(100, 0, 0)
        self.assertEqual(transport.edge_cost(1, 2, "railroad"), 5)

    def test_planned_candidate_requires_explicit_complete_same_network_baseline(self):
        transport = context(mode=TransportMode.HIGHEST_UNLOCKED, advances={"railroad_advance"})
        locations = {node: location(node) for node in (1, 2, 3)}
        graph = {1: {2}, 2: {1, 3}, 3: {2}}
        with self.assertRaisesRegex(TransportInputError, "baseline propagated"):
            evaluate_candidate(3, locations, graph, {}, transport_context=transport)
        with self.assertRaisesRegex(TransportInputError, "omits locations"):
            evaluate_candidate(3, locations, graph, {}, transport_context=transport, baseline_proximity={1: 100})
        baseline = propagate_proximity({1: 100}, locations, graph, {}, transport_context=transport)
        result = evaluate_candidate(3, locations, graph, {}, transport_context=transport, baseline_proximity=baseline)
        self.assertEqual(result.score, 0)
        # Both cheap shortlist demand and final candidate score use the same
        # planned baseline; a zero live snapshot cannot manufacture improvement.
        ranked = rank_local_candidates((2, 3), locations, graph, {}, transport_context=transport, baseline_proximity=baseline)
        self.assertTrue(all(result.score == 0 for result in ranked))

    def test_relocation_reconstructs_both_layouts_with_same_planned_roads(self):
        transport = context(mode=TransportMode.HIGHEST_UNLOCKED, advances={"railroad_advance"})
        locations = {node: location(node, proximity=0) for node in (1, 2, 3)}
        graph = {1: {2}, 2: {1, 3}, 3: {2}}
        proposal = evaluate_migration_pair(1, 3, {1: 80}, locations, graph, {}, transport_context=transport)
        self.assertEqual(proposal.current_score, 225)
        self.assertEqual(proposal.recommended_score, 225)
        self.assertEqual(proposal.net_gain, 0)
        # Changing only the actual cached Proximity cannot affect a planned
        # comparison. Endpoints are symmetric in this independent fixture.
        changed_live = {node: replace(value, proximity=100) for node, value in locations.items()}
        self.assertEqual(proposal, evaluate_migration_pair(1, 3, {1: 80}, changed_live, graph, {}, transport_context=transport))


if __name__ == "__main__":
    unittest.main()
