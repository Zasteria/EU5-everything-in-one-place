from pathlib import Path
import copy
import json
import re
import tempfile
import unittest

from src.eu5autobuild.catalog_builder import extract_player_manageable_buildings
from src.eu5autobuild.game_root import configured_game_root
from src.eu5autobuild.policy import (
    BuildingCatalog,
    Policy,
    REQUIRED_POLICY_KEYS,
    RgoPolicy,
    load_building_catalog,
    load_policies,
)
from src.eu5autobuild.validation import load_json


ROOT = Path(__file__).resolve().parents[1]


def _top_level_script_ids(directory: Path) -> set[str]:
    ids: set[str] = set()
    for path in directory.glob("*.txt"):
        text = re.sub(r"#.*", "", path.read_text(encoding="utf-8-sig", errors="ignore"))
        ids.update(re.findall(r"(?m)^\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*\{", text))
    return ids


class PolicyTests(unittest.TestCase):
    def _raw_policy(self):
        return json.loads(
            (ROOT / "policies" / "templates.json").read_text(encoding="utf-8")
        )["policies"][0]

    def test_default_templates_exist(self):
        policies = load_policies(ROOT / "policies" / "templates.json")
        self.assertEqual(
            [policy.id for policy in policies],
            [
                "granary",
                "industrial_zone",
                "trade_center",
                "naval_base",
                "frontier",
                "food_priority",
                "military_industry",
                "shipbuilding",
                "textiles",
                "mining",
                "luxury_goods",
            ],
        )

    def test_schema_has_required_fields(self):
        policies = load_policies(ROOT / "policies" / "templates.json")
        raw_policies = json.loads(
            (ROOT / "policies" / "templates.json").read_text(encoding="utf-8")
        )["policies"]
        for policy in policies:
            self.assertTrue(policy.id)
            self.assertTrue(policy.priority_goods)
            self.assertTrue(policy.prediction.get("display_name"))
            self.assertEqual(policy.job_fill_deadline_months, 12)
            self.assertEqual(policy.native_input_priority, 5)

        runtime_keys = {
            "budget",
            "price_band",
            "allow_special_buildings",
            "pause_on_labor_shortage",
            "pause_on_input_shortage",
            "input_shortage_strategy",
            "job_fill_deadline_months",
            "native_input_priority",
            "rgo",
        }
        self.assertTrue(runtime_keys.isdisjoint(REQUIRED_POLICY_KEYS))
        for raw in raw_policies:
            self.assertTrue(runtime_keys.isdisjoint(raw))

    def test_template_schema_rejects_missing_strategy_field(self):
        raw = self._raw_policy()
        raw.pop("priority_goods")
        with self.assertRaisesRegex(ValueError, "priority_goods"):
            Policy.from_mapping(raw)

    def test_policy_validation_rejects_unsafe_or_ambiguous_values(self):
        cases = (
            ("invalid id", lambda raw: raw.update(id="bad id"), "script identifier"),
            (
                "invalid goods list",
                lambda raw: raw.update(priority_goods="wheat"),
                "list of script identifiers",
            ),
            (
                "duplicate building",
                lambda raw: raw["allowed_buildings"].append(raw["allowed_buildings"][0]),
                "duplicate ids",
            ),
            (
                "empty summary",
                lambda raw: raw["prediction"].update(summary=" "),
                "must be non-empty text",
            ),
        )
        for label, mutate, message in cases:
            with self.subTest(label=label):
                raw = copy.deepcopy(self._raw_policy())
                mutate(raw)
                with self.assertRaisesRegex(ValueError, message):
                    Policy.from_mapping(raw)

    def test_rgo_validation_rejects_invalid_values(self):
        cases = (
            ({"allowed": "yes"}, "must be a boolean"),
            ({"minimum_utilization": float("nan")}, "must be finite"),
        )
        for raw, message in cases:
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(ValueError, message):
                    RgoPolicy.from_mapping(raw)

    def test_building_catalog_rejects_duplicate_and_dangling_entries(self):
        building = {
            "id": "test_building",
            "output_goods": ["tools"],
            "input_goods": ["iron"],
            "workforce_pop_types": ["laborers"],
            "is_special": False,
            "localization_key": "test_building",
            "age": 1,
        }
        cases = (
            ({"buildings": []}, "at least one"),
            ({"buildings": [building, dict(building)]}, "duplicate id"),
            (
                {"buildings": [{**building, "age": 7}]},
                "invalid ages",
            ),
            (
                {"buildings": [{**building, "is_special": "false"}]},
                "must be a boolean",
            ),
            (
                {
                    "buildings": [building],
                    "source_buildings_by_good": {"tools": ["missing_building"]},
                },
                "are unknown",
            ),
        )
        for raw, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    BuildingCatalog.from_mapping(copy.deepcopy(raw))

    def test_json_loader_reports_invalid_and_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text('{"value": NaN}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-finite JSON number"):
                load_json(path)
            path.write_text('{"value":', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid JSON"):
                load_json(path)
            path.write_text('{"value": 1, "value": 2}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate JSON key: value"):
                load_json(path)

    def test_building_catalog_covers_policy_buildings(self):
        policies = load_policies(ROOT / "policies" / "templates.json")
        catalog = load_building_catalog(ROOT / "policies" / "building_catalog.json")
        catalog_ids = set(catalog.buildings)
        for policy in policies:
            referenced = set(policy.allowed_buildings) | set(policy.banned_buildings)
            self.assertFalse(referenced - catalog_ids, f"{policy.id} missing catalog entries")
            self.assertFalse(
                set(policy.allowed_buildings) & set(policy.banned_buildings),
                f"{policy.id} cannot both allow and ban the same building",
            )
        for building in catalog.buildings.values():
            self.assertTrue(building.localization_key)
            self.assertIn(building.age, range(1, 7))
        self.assertGreater(len(catalog.buildings), 56)
        self.assertIn("star_fort", catalog.buildings)
        self.assertIn("fortress", catalog.buildings)
        self.assertEqual({building.age for building in catalog.buildings.values()}, set(range(1, 7)))

        self.assertIn(
            "tools_workshop",
            catalog.consumer_buildings_by_good["iron"],
        )
        self.assertIn(
            "iron_foundry",
            catalog.consumer_buildings_by_good["coal"],
        )

    def test_catalog_matches_local_eu5_data_when_available(self):
        game_dir = configured_game_root()
        if game_dir is None:
            self.skipTest("Set EU5_GAME_ROOT to run installed-game integration tests")
        common_dir = game_dir / "game" / "in_game" / "common"
        if not common_dir.exists():
            self.skipTest("Local EU5 game data not found")

        policies = load_policies(ROOT / "policies" / "templates.json")
        catalog = load_building_catalog(ROOT / "policies" / "building_catalog.json")
        real_building_ids = _top_level_script_ids(common_dir / "building_types")
        self.assertEqual(
            set(catalog.buildings),
            set(extract_player_manageable_buildings(game_dir)),
        )
        good_ids = _top_level_script_ids(common_dir / "goods")
        pop_type_ids = _top_level_script_ids(common_dir / "pop_types")

        self.assertFalse(set(catalog.buildings) - real_building_ids)
        self.assertFalse(
            {
                good
                for building in catalog.buildings.values()
                for good in building.output_goods
            }
            - good_ids
        )
        self.assertFalse(
            {
                good
                for building in catalog.buildings.values()
                for good in building.input_goods
            }
            - good_ids
        )
        self.assertFalse(
            {
                pop_type
                for building in catalog.buildings.values()
                for pop_type in building.workforce_pop_types
            }
            - pop_type_ids
        )
        self.assertFalse(
            {good for policy in policies for good in policy.priority_goods}
            - good_ids
        )
        self.assertFalse(set(catalog.source_buildings_by_good) - good_ids)
        self.assertFalse(
            {
                building_id
                for source_building_ids in catalog.source_buildings_by_good.values()
                for building_id in source_building_ids
            }
            - real_building_ids
        )
        self.assertFalse(set(catalog.consumer_buildings_by_good) - good_ids)
        self.assertFalse(
            {
                building_id
                for consumer_building_ids in catalog.consumer_buildings_by_good.values()
                for building_id in consumer_building_ids
            }
            - real_building_ids
        )
        for good, building_ids in catalog.consumer_buildings_by_good.items():
            for building_id in building_ids:
                self.assertIn(good, catalog.buildings[building_id].input_goods)
        localization_dir = game_dir / "game" / "main_menu" / "localization" / "simp_chinese"
        localization_keys = set()
        for path in localization_dir.glob("*.yml"):
            text = path.read_text(encoding="utf-8-sig", errors="ignore")
            localization_keys.update(
                re.findall(r"(?m)^\s*([A-Za-z0-9_]+):", text)
            )
        self.assertTrue(localization_keys, "EU5 simplified Chinese localization was not found")
        self.assertFalse(
            {building.localization_key for building in catalog.buildings.values()}
            - localization_keys
        )


if __name__ == "__main__":
    unittest.main()
