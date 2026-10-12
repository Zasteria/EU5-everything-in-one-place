"""Schema-2 transport inputs and validator mode boundaries."""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from scripts.validate_governor_save import (
    RawLocation, SaveSnapshot, build_transport_context, validate,
)
from src.eu5autobuild.governor_transport import TransportInputError
from tests.test_governor_save_validator import parse_text, runtime_block


def snapshot_fixture():
    country = {
        "eu5ab_gov_transport_schema": 2,
        "eu5ab_gov_transport_road_tier": 4,
        "eu5ab_gov_cached_global_speed": .5,
        "eu5ab_gov_cached_land_speed": .1,
        "eu5ab_gov_cached_road_base": 20,
        "eu5ab_gov_cached_land_base": 40,
        "eu5ab_gov_cached_lake_base": 4,
    }
    locations = {}
    for node in (1, 2, 3):
        locations[node] = RawLocation(node, owner=764, rank="city", road_to_capital=True,
                                      runtime_variables={
                                          "eu5ab_gov_cached_local_speed": 0,
                                          "eu5ab_gov_cached_topography": -.25 if node == 1 else 0,
                                          "eu5ab_gov_cached_topography_impact": 0,
                                          "eu5ab_gov_cached_vegetation": -.3,
                                          "eu5ab_gov_node_value": 100,
                                      })
    return SaveSnapshot(player_country_id=764, capitals={764: 1}, locations=locations,
                        country_runtime_variables={764: country},
                        buildings={"local_governor": {2}},
                        building_levels={"local_governor": {2: 1}})


class SaveTransportTests(unittest.TestCase):
    def test_country_fixed_point_cache_and_omitted_zero(self):
        text = ('date=1429.3.1\nversion="1.3.11"\nprevious_played={ {\n\tidtype=764\n'
                'countries={\n764={\n\tcapital=1\n'
                + runtime_block([
                    ("eu5ab_gov_transport_schema", "value", "identity=200000"),
                    ("eu5ab_gov_cached_land_speed", "value", ""),
                    ("eu5ab_gov_cached_global_speed", "value", "identity=53600"),
                ], indent=1)
                + '}\nmarket_manager={\n}\n')
        snapshot = parse_text(text)
        self.assertEqual(snapshot.capitals[764], 1)
        self.assertEqual(snapshot.country_runtime_variables[764], {
            "eu5ab_gov_transport_schema": 2,
            "eu5ab_gov_cached_land_speed": 0,
            "eu5ab_gov_cached_global_speed": .536,
        })

    def test_legacy_requires_historical_factors_not_schema_two(self):
        self.assertIsNone(build_transport_context(SaveSnapshot(), set(), {}, set(), mode="legacy"))
        with self.assertRaisesRegex(TransportInputError, "cannot replay legacy"):
            build_transport_context(snapshot_fixture(), {1, 2, 3}, {}, set(), mode="legacy")

    def test_new_modes_reject_incomplete_or_old_inputs(self):
        for missing in ("eu5ab_gov_transport_schema", "eu5ab_gov_cached_global_speed",
                        "eu5ab_gov_cached_land_base", "eu5ab_gov_cached_lake_base"):
            with self.subTest(missing=missing):
                snapshot = snapshot_fixture()
                del snapshot.country_runtime_variables[764][missing]
                with self.assertRaises(TransportInputError):
                    build_transport_context(snapshot, {1, 2, 3}, {}, set(), mode="highest-unlocked")
        snapshot = snapshot_fixture()
        del snapshot.locations[2].runtime_variables["eu5ab_gov_cached_topography_impact"]
        snapshot.locations[2].runtime_variables["eu5ab_gov_edge_cost_factor"] = .01
        with self.assertRaisesRegex(TransportInputError, "location 2"):
            build_transport_context(snapshot, {1, 2, 3}, {}, set(), mode="actual")

    def test_highest_road_covers_roadless_land_but_not_lake_or_strait(self):
        snapshot = snapshot_fixture()
        graph = {1: {2, 9}, 2: {1, 3}, 3: {2, 9}, 9: {1, 3}}
        special = {frozenset((2, 3))}
        high = build_transport_context(snapshot, {1, 2, 3}, graph, special,
                                       mode="highest-unlocked", lake_ids={9})
        actual = build_transport_context(snapshot, {1, 2, 3}, graph, special,
                                         mode="actual", lake_ids={9})
        self.assertEqual(high.planned_road_type, "railroad")
        self.assertAlmostEqual(high.edge_cost(1, 2, None), 5/.75/1.6)
        self.assertAlmostEqual(actual.edge_cost(1, 2, None), 40/.5/1.6)
        self.assertEqual(high.edge_cost(1, 9, None), actual.edge_cost(1, 9, None))
        self.assertEqual(high.edge_cost(9, 3, None), 4/1.5)
        with self.assertRaises(TransportInputError):
            high.edge_cost(2, 3, None)

    def test_topography_specific_country_modifier_is_preserved(self):
        snapshot = snapshot_fixture()
        snapshot.locations[1].runtime_variables["eu5ab_gov_cached_topography_impact"] = 1
        ctx = build_transport_context(snapshot, {1, 2, 3}, {1: {2}, 2: {1}}, set(),
                                      mode="highest-unlocked")
        self.assertAlmostEqual(ctx.edge_cost(1, 2, None), 5/.5/1.6)

    def test_unknown_or_foreign_water_path_is_rejected(self):
        with self.assertRaisesRegex(TransportInputError, "Unclassified"):
            build_transport_context(snapshot_fixture(), {1, 2, 3}, {1: {99}}, set(), mode="actual")

    def test_incomplete_inputs_stop_before_graph_or_output(self):
        snapshot = snapshot_fixture()
        del snapshot.country_runtime_variables[764]["eu5ab_gov_transport_schema"]
        with patch("scripts.validate_governor_save.parse_save", return_value=snapshot), \
             patch("scripts.validate_governor_save.resolve_game_layer", return_value=Path("unused")), \
             patch("scripts.validate_governor_save.parse_location_templates", return_value=({}, {})), \
             patch("scripts.validate_governor_save.parse_ports", return_value=set()), \
             patch("scripts.validate_governor_save.build_owned_adjacency") as graph, \
             patch.object(Path, "write_text") as write, patch("builtins.print"):
            self.assertEqual(validate(Path("unused.eu5"), Path("unused"), "mixed",
                                      layout_report=Path("unused.json"), transport_mode="actual"), 2)
            graph.assert_not_called()
            write.assert_not_called()

    def test_report_distinguishes_actual_error_and_planned_scores(self):
        for mode in ("actual", "highest-unlocked"):
            with self.subTest(mode=mode):
                snapshot = snapshot_fixture()
                names = {1: "one", 2: "two", 3: "three", 9: "lake"}
                attrs = {"lake": {"topography": "lakes"}}
                graph = {1: {2, 9}, 2: {1, 3}, 3: {2, 9}, 9: {1, 3}}
                with patch("scripts.validate_governor_save.parse_save", return_value=snapshot), \
                     patch("scripts.validate_governor_save.resolve_game_layer", return_value=Path("unused")), \
                     patch("scripts.validate_governor_save.parse_location_templates", return_value=(names, attrs)), \
                     patch("scripts.validate_governor_save.parse_ports", return_value=set()), \
                     patch("scripts.validate_governor_save.build_owned_adjacency", return_value=(deepcopy(graph), set())), \
                     patch("scripts.validate_governor_save.load_chinese_names", return_value={}), \
                     patch.object(Path, "mkdir"), patch.object(Path, "write_text") as write, patch("builtins.print"):
                    self.assertEqual(validate(Path("unused.eu5"), Path("unused"), "mixed",
                                              layout_report=Path("unused.json"), transport_mode=mode), 0)
                    report = json.loads(write.call_args.args[0])
                self.assertEqual(report["transport_mode"], mode)
                self.assertEqual(report["lake_transit_nodes"], 1)
                self.assertEqual(report["experiments"], {})
                self.assertEqual(report["generated_runtime"]["status"], "not_run")
                error = report["complete_layout"]["live_model_absolute_weighted_error"]
                self.assertEqual(error is None, mode == "highest-unlocked")


if __name__ == "__main__":
    unittest.main()
