from pathlib import Path
import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.eu5autobuild.catalog_builder import (
    _replace_rules_priority_section,
    build_priority_overrides,
    build_catalog_payload,
    extract_player_manageable_buildings,
    generated_catalog_and_rules,
    is_player_manageable_building,
)
from src.eu5autobuild.game_root import configured_game_root
from src.eu5autobuild.game_data import parse_paradox_script
from src.eu5autobuild.food_infrastructure import NON_RECIPE_FOOD_BUILDINGS, RGO_BOOST_GOODS


ROOT = Path(__file__).resolve().parents[1]
GAME_ROOT = configured_game_root()
HAS_INSTALLED_GAME = bool(
    GAME_ROOT is not None
    and (GAME_ROOT / "game" / "in_game" / "common").is_dir()
)


def _block(text: str):
    return parse_paradox_script(f"test = {{ {text} }}")[0][1]


class CatalogBuilderTests(unittest.TestCase):
    def test_refresh_replaces_stale_fields_and_indexes_all_candidate_methods(self):
        definitions = {
            "fixture": (_block("max_levels = 1"), "normal.txt"),
            "local_smelters": (_block("max_levels = 1"), "normal.txt"),
        }
        models = {
            "fixture": SimpleNamespace(slots=((
                SimpleNamespace(outputs={"paper": 1}, inputs={"lumber": 1}),
                SimpleNamespace(outputs={"books": 1}, inputs={"leather": 1}),
            ),)),
            "local_smelters": SimpleNamespace(slots=()),
        }
        previous = {
            "buildings": [{"id": "fixture", "output_goods": ["silk"],
                           "workforce_pop_types": ["clergy"], "is_special": True},
                          {"id": "retired"}],
            "input_goods_by_building": {"fixture": ["lumber"]},
            "source_buildings_by_good": {"paper": ["retired"], "silk": ["fixture"]},
        }
        module = "src.eu5autobuild.catalog_builder."
        workforce = SimpleNamespace(buildings={"fixture": SimpleNamespace(pop_types=("peasants",))})
        with (patch(module + "extract_player_manageable_buildings", return_value=definitions),
              patch(module + "extract_production_models", return_value=models),
              patch(module + "extract_workforce_model", return_value=workforce),
              patch(module + "extract_building_unlock_ages", return_value={"fixture": 3})):
            refreshed = build_catalog_payload(Path("unused"), previous)
        rows = {row['id']: row for row in refreshed['buildings']}
        self.assertEqual(rows['fixture']['output_goods'], ['books', 'paper'])
        self.assertEqual(rows['fixture']['workforce_pop_types'], ['peasants'])
        self.assertEqual(rows['fixture']['age'], 3)
        self.assertNotIn('is_special', rows['fixture'])
        self.assertNotIn('retired', rows)
        self.assertEqual(refreshed['input_goods_by_building']['fixture'], ['leather', 'lumber'])
        self.assertEqual(refreshed['source_buildings_by_good'], {
            'books': ['fixture'], 'copper': ['local_smelters'], 'paper': ['fixture'],
        })

    def test_player_manageable_filter_excludes_event_proxies_and_estate_buildings(self):
        self.assertTrue(
            is_player_manageable_building(_block("max_levels = 1"), "forts.txt")
        )
        self.assertFalse(
            is_player_manageable_building(
                _block("max_levels = 1"), "event_only_buildings.txt"
            )
        )
        self.assertFalse(
            is_player_manageable_building(
                _block("estate = estate_type:nobles"), "other.txt"
            )
        )
        self.assertFalse(
            is_player_manageable_building(
                _block("country_potential = { always = no }"), "other.txt"
            )
        )

    def test_catalog_excludes_unsafe_settlement_lifecycle_building(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            buildings = root / "game" / "in_game" / "common" / "building_types"
            buildings.mkdir(parents=True)
            (buildings / "rural_buildings.txt").write_text(
                "normal = { max_levels = 1 }\n"
                "settlement_building = { max_levels = 1 rural_settlement = yes }\n",
                encoding="utf-8",
            )

            extracted = extract_player_manageable_buildings(root)

        self.assertIn("normal", extracted)
        self.assertNotIn("settlement_building", extracted)

    def test_priority_inheritance_uses_zero_for_independent_and_max_for_merged_chains(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            buildings = root / "game" / "in_game" / "common" / "building_types"
            buildings.mkdir(parents=True)
            (buildings / "test.txt").write_text(
                """
                calibrated = { }
                independent = { }
                upgrade = { obsolete = calibrated }
                merged = { obsolete = independent obsolete = upgrade }
                """,
                encoding="utf-8",
            )
            priorities, provenance = build_priority_overrides(
                root,
                {"calibrated", "independent", "upgrade", "merged"},
                {"direct_video_priorities": {"calibrated": 8}},
            )

        self.assertEqual(priorities["independent"], 0)
        self.assertEqual(priorities["upgrade"], 8)
        self.assertEqual(priorities["merged"], 8)
        self.assertEqual(provenance["independent"], "independent_default")
        self.assertEqual(provenance["upgrade"], "inherited_upgrade")

    def test_priority_inheritance_rejects_upgrade_cycles(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            buildings = root / "game" / "in_game" / "common" / "building_types"
            buildings.mkdir(parents=True)
            (buildings / "cycle.txt").write_text(
                "a = { obsolete = b }\nb = { obsolete = a }\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Building upgrade cycle"):
                build_priority_overrides(
                    root,
                    {"a", "b"},
                    {"direct_video_priorities": {}},
                )

    def test_priority_input_rejects_nonfinite_out_of_range_and_nonidentifier_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            buildings = root / "game" / "in_game" / "common" / "building_types"
            buildings.mkdir(parents=True)
            (buildings / "test.txt").write_text("test = { }\n", encoding="utf-8")
            invalid_cases = (
                ({"direct_video_priorities": {"test": float("nan")}}, "must be finite"),
                ({"direct_video_priorities": {"test": 11}}, "between 0 and 10"),
                ({"direct_video_priorities": {"not valid": 5}}, "valid script identifier"),
            )
            for payload, message in invalid_cases:
                with self.subTest(message=message):
                    with self.assertRaisesRegex(ValueError, message):
                        build_priority_overrides(root, {"test"}, payload)

    def test_priority_json_replacement_handles_escaped_braces_and_rejects_unbalanced_input(self):
        original = json.dumps(
            {
                "note": 'a } and an escaped " quote',
                "building_priorities": {"old": {"value": 1}},
                "tail": True,
            },
            indent=2,
        )
        replacement = {"minimum": 0, "overrides": {"test": 2}}

        updated = _replace_rules_priority_section(original, replacement)

        self.assertEqual(json.loads(updated)["building_priorities"], replacement)
        self.assertTrue(json.loads(updated)["tail"])
        with self.assertRaisesRegex(ValueError, "Unbalanced"):
            _replace_rules_priority_section(
                '{"building_priorities": {"minimum": 0',
                replacement,
            )


@unittest.skipUnless(
    HAS_INSTALLED_GAME,
    "Set EU5_GAME_ROOT to run installed-game integration tests",
)
class InstalledGameCatalogBuilderTests(unittest.TestCase):
    def test_legacy_food_hints_are_removed_and_reviewed_boosts_match_vanilla(self):
        payload = json.loads((ROOT / 'policies/building_catalog.json').read_text(encoding='utf-8'))
        for item in payload['buildings']:
            if item['id'] in NON_RECIPE_FOOD_BUILDINGS:
                item['output_goods'] = ['wheat', 'rice']
        payload['source_buildings_by_good']['wheat'] = sorted(NON_RECIPE_FOOD_BUILDINGS)
        rebuilt = build_catalog_payload(GAME_ROOT, payload)
        for item in rebuilt['buildings']:
            if item['id'] in NON_RECIPE_FOOD_BUILDINGS:
                self.assertEqual(item['output_goods'], [])
        self.assertFalse(any(NON_RECIPE_FOOD_BUILDINGS.intersection(ids)
                             for ids in rebuilt['source_buildings_by_good'].values()))
        definitions = extract_player_manageable_buildings(GAME_ROOT)
        for building, goods in RGO_BOOST_GOODS.items():
            block, _ = definitions[building]
            modifier = dict(next(value for key, value in block if key == 'modifier'))
            actual = {key.removeprefix('local_').removesuffix('_output_modifier')
                      for key, value in modifier.items()
                      if key.endswith('_output_modifier') and value > 0}
            self.assertEqual(actual, set(goods))

    def test_checked_in_catalog_and_priorities_match_vanilla_generation(self):
        if GAME_ROOT is None:
            raise RuntimeError("EU5 game root is required for installed-game catalog tests")
        catalog_text, rules_text, provenance = generated_catalog_and_rules(GAME_ROOT)
        self.assertEqual(
            (ROOT / "policies" / "building_catalog.json").read_text(encoding="utf-8"),
            catalog_text,
        )
        self.assertEqual(
            (ROOT / "policies" / "automation_rules.json").read_text(encoding="utf-8"),
            rules_text,
        )
        catalog = json.loads(catalog_text)
        rules = json.loads(rules_text)
        ids = {item["id"] for item in catalog["buildings"]}
        priorities = rules["building_priorities"]["overrides"]
        self.assertIn("star_fort", ids)
        self.assertIn("fortress", ids)
        self.assertNotIn("cathedral", ids)
        self.assertNotIn("castel_sant_angelo", ids)
        self.assertNotIn("settlement_building", ids)
        self.assertEqual(priorities["star_fort"], 0)
        self.assertEqual(priorities["fortress"], 0)
        self.assertEqual(priorities["commerce_center"], priorities["marketplace"])
        self.assertEqual(set(priorities), ids)
        self.assertEqual(set(provenance), ids)


if __name__ == "__main__":
    unittest.main()
