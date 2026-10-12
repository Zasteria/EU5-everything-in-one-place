from pathlib import Path
import json
import tempfile
import unittest

from src.eu5autobuild.policy import load_building_catalog
from src.eu5autobuild.rules import AutomationRules, load_automation_rules


ROOT = Path(__file__).resolve().parents[1]


class AutomationRulesTests(unittest.TestCase):
    def _raw_rules(self):
        return json.loads(
            (ROOT / "policies" / "automation_rules.json").read_text(encoding="utf-8")
        )

    def test_default_rules_load_and_expose_essential_groups(self):
        rules = load_automation_rules(ROOT / "policies" / "automation_rules.json")
        self.assertEqual(rules.schema_version, 5)
        self.assertEqual(rules.cadence.deep_score_location_limit, 600)
        self.assertEqual(rules.cadence.deep_score_quota_multiplier, 8)
        self.assertEqual(rules.cadence.candidates_per_location, 3)
        self.assertEqual(rules.cadence.actual_profit_candidates_per_location, 10)
        self.assertIn("wheat", rules.food_goods)
        self.assertIn("masonry", rules.construction_goods)
        self.assertIn("weaponry", rules.essential_goods)
        self.assertIn("tools", rules.input_goods)
        self.assertEqual(rules.cadence.max_country_concurrent_projects, 600)
        self.assertEqual(rules.thresholds.rgo_budget_cost, 100)
        self.assertEqual(rules.thresholds.upgrade_replacement_bonus, 5000)
        self.assertEqual(rules.thresholds.engine_min_annual_return_ratio, 0.05)
        self.assertEqual(rules.thresholds.construction_price_ceiling_ratio, 1.5)
        self.assertEqual(rules.thresholds.construction_stall_headroom_ratio, 0.75)
        self.assertEqual(rules.workforce_model.default_fill_deadline_months, 12)
        self.assertEqual(rules.workforce_model.maximum_fill_deadline_months, 240)
        self.assertEqual(rules.workforce_model.max_penalty, 1200)
        self.assertEqual(rules.workforce_model.strategic_relief, 0.5)
        self.assertEqual(rules.native_input_fit.default_priority, 5)
        self.assertEqual(rules.native_input_fit.maximum_priority, 10)
        self.assertEqual(rules.native_input_fit.max_bonus, 500)
        self.assertEqual(rules.goods_groups_for("wheat"), frozenset({"food"}))
        self.assertIn("food", rules.building_groups_for("granary"))

    def test_building_quality_priorities_cover_catalog_with_default_zero(self):
        rules = load_automation_rules(ROOT / "policies" / "automation_rules.json")
        catalog = load_building_catalog(ROOT / "policies" / "building_catalog.json")
        self.assertEqual(rules.building_priority_for("granary"), 10)
        self.assertEqual(rules.building_priority_for("fruit_orchard"), 0)
        self.assertEqual(rules.building_priority_for("stockade"), 0)
        self.assertEqual(rules.building_priority_for("castle"), 0)
        self.assertEqual(rules.building_priority_for("bastion"), 0)
        self.assertEqual(rules.building_priority_for("star_fort"), 0)
        self.assertEqual(rules.building_priority_for("fortress"), 0)
        self.assertEqual(rules.building_priority_for("city_walls"), 0)
        self.assertEqual(rules.building_priority_for("porcelain_manufactory"), 0)
        self.assertEqual(rules.building_priority_for("commerce_center"), 6)
        self.assertEqual(rules.building_priority_for("not_in_catalog"), 0)
        self.assertEqual(set(rules.building_priorities.overrides), set(catalog.buildings))
        self.assertEqual(rules.building_priorities.score_per_point, 50)
        self.assertTrue(
            all(0 <= rules.building_priority_for(building_id) <= 10 for building_id in catalog.buildings)
        )

    def test_calibrated_production_chains_keep_consistent_priorities(self):
        rules = load_automation_rules(ROOT / "policies" / "automation_rules.json")
        expected_chains = {
            1: ("steel_mill",),
            0.3: ("hand_cannon_guild", "gun_smith", "guns_workshop", "firearms_manufactory", "firearms_factory"),
            6: (
                "scriptorium",
                "printing_press_shop",
                "printing_manufactory",
                "printing_mill",
                "charcoal_maker",
                "improved_charcoal_maker",
            ),
            7: (
                "sheep_farms",
                "paper_guild",
                "paper_workshop",
                "paper_manufactory",
                "paper_mill",
            ),
            8: (
                "rural_clothmaker",
                "cloth_guild",
                "cloth_workshop",
                "cloth_manufactory",
                "textile_mill",
                "lumber_mill",
                "bog_iron_smelter",
            ),
            9: (
                "fine_cloth_guild",
                "fine_cloth_workshop",
                "fine_cloth_manufactory",
                "fine_cloth_mill",
                "tools_guild",
                "tools_workshop",
                "iron_foundry",
                "iron_mill",
            ),
        }
        for expected, building_ids in expected_chains.items():
            with self.subTest(expected=expected):
                self.assertEqual(
                    {rules.building_priority_for(building_id) for building_id in building_ids},
                    {expected},
                )

    def test_needs_scores_dominate_profit_scores(self):
        rules = load_automation_rules(ROOT / "policies" / "automation_rules.json")
        self.assertGreater(rules.scores.food_emergency, rules.scores.high_profit * 10)
        self.assertGreater(rules.scores.critical_construction_good, rules.scores.high_profit * 10)

    def test_schema_two_rules_keep_loading_with_v3_runtime_defaults(self):
        raw = json.loads((ROOT / "policies" / "automation_rules.json").read_text(encoding="utf-8"))
        raw["schema_version"] = 2
        for key in (
            "max_country_concurrent_projects",
            "deep_score_location_limit",
            "deep_score_quota_multiplier",
            "candidates_per_location",
            "actual_profit_candidates_per_location",
        ):
            raw["cadence"].pop(key)
        raw["thresholds"].pop("economic_score_scale")
        raw["thresholds"].pop("upgrade_replacement_bonus")
        raw.pop("location_scores")
        raw.pop("failure_cooldowns")
        raw.pop("rgo_scores")
        raw.pop("workforce_model")
        raw.pop("native_input_fit")

        rules = AutomationRules.from_mapping(raw)

        self.assertEqual(rules.schema_version, 2)
        self.assertEqual(rules.cadence.max_country_concurrent_projects, 600)
        self.assertEqual(rules.cadence.deep_score_location_limit, 600)
        self.assertEqual(rules.cadence.deep_score_quota_multiplier, 8)
        self.assertEqual(rules.cadence.candidates_per_location, 3)
        self.assertEqual(rules.cadence.actual_profit_candidates_per_location, 10)
        self.assertEqual(rules.thresholds.upgrade_replacement_bonus, 5000)
        self.assertEqual(rules.location_scores.waiting_per_month, 8)
        self.assertEqual(rules.workforce_model.default_fill_deadline_months, 12)
        self.assertEqual(rules.workforce_model.maximum_fill_deadline_months, 240)
        self.assertEqual(rules.native_input_fit.default_priority, 5)
        self.assertEqual(rules.native_input_fit.maximum_priority, 10)

    def test_rejects_inverted_supply_thresholds(self):
        raw = json.loads((ROOT / "policies" / "automation_rules.json").read_text(encoding="utf-8"))
        raw["thresholds"]["goods_critical_supply_ratio"] = 0.95
        raw["thresholds"]["goods_shortage_supply_ratio"] = 0.9
        with self.assertRaisesRegex(ValueError, "critical < shortage"):
            AutomationRules.from_mapping(raw)

    def test_country_concurrent_limit_allows_600_but_rejects_601(self):
        raw = json.loads((ROOT / "policies" / "automation_rules.json").read_text(encoding="utf-8"))
        raw["cadence"]["max_country_concurrent_projects"] = 600
        self.assertEqual(
            AutomationRules.from_mapping(raw).cadence.max_country_concurrent_projects,
            600,
        )
        raw["cadence"]["max_country_concurrent_projects"] = 601
        with self.assertRaisesRegex(ValueError, "cannot exceed 600"):
            AutomationRules.from_mapping(raw)

    def test_rejects_invalid_cadence_settings(self):
        cases = (
            ("max_country_concurrent_projects", 0, "must be positive"),
            ("deep_score_location_limit", 601, "cannot exceed 600"),
            ("deep_score_quota_multiplier", 0, "must be positive"),
            ("candidates_per_location", 2, "exactly three"),
            (
                "actual_profit_candidates_per_location",
                2,
                "cannot be below",
            ),
            (
                "actual_profit_candidates_per_location",
                31,
                "cannot exceed 30",
            ),
            ("location_cooldown_months", -1, "cannot be negative"),
            ("deep_score_quota_multiplier", "8", "must be an integer"),
        )
        for key, value, message in cases:
            with self.subTest(key=key):
                raw = self._raw_rules()
                raw["cadence"][key] = value
                with self.assertRaisesRegex(ValueError, message):
                    AutomationRules.from_mapping(raw)

    def test_rejects_invalid_threshold_settings(self):
        cases = (
            ("food_emergency_ratio", 0.9, "emergency < low"),
            ("input_shortage_supply_ratio", 0, r"in \(0, 1\]"),
            ("goods_high_price_ratio", 1, "greater than"),
            ("minimum_unemployed_workers", -1, "cannot be negative"),
            ("expansion_bonus_per_level", -1, "cannot be negative"),
            ("rgo_budget_cost", 0, "must be positive"),
            ("high_profit", -2, "cannot be below"),
            ("economic_score_scale", 0, "must be positive"),
            ("engine_min_annual_return_ratio", 1.1, "between 0 and 1"),
            ("construction_price_ceiling_ratio", 1, "exceed"),
            ("construction_stall_headroom_ratio", 0, r"in \(0, 1\]"),
            ("high_profit", float("inf"), "must be finite"),
        )
        for key, value, message in cases:
            with self.subTest(key=key, value=value):
                raw = self._raw_rules()
                raw["thresholds"][key] = value
                with self.assertRaisesRegex(ValueError, message):
                    AutomationRules.from_mapping(raw)

    def test_rejects_invalid_score_sections(self):
        cases = (
            (
                lambda raw: raw["scores"].pop("food_emergency"),
                "missing keys",
            ),
            (
                lambda raw: raw["scores"].update(input_shortage_penalty=1),
                "must be penalties",
            ),
            (
                lambda raw: raw["scores"].update(food_emergency=-1),
                "cannot be negative",
            ),
            (
                lambda raw: raw["location_scores"].update(waiting_per_month=0),
                "must be positive",
            ),
            (
                lambda raw: raw["location_scores"].update(recent_build_penalty=1),
                "must be a penalty",
            ),
            (
                lambda raw: raw["failure_cooldowns"].update(workforce=-1),
                "cannot be negative",
            ),
            (
                lambda raw: raw["rgo_scores"].update(cost_penalty=1),
                "must be a penalty",
            ),
        )
        for mutate, message in cases:
            with self.subTest(message=message):
                raw = self._raw_rules()
                mutate(raw)
                with self.assertRaisesRegex(ValueError, message):
                    AutomationRules.from_mapping(raw)

    def test_rejects_invalid_workforce_and_native_input_models(self):
        cases = (
            (
                "workforce_model",
                "default_fill_deadline_months",
                241,
                "between 0 and 240",
            ),
            (
                "workforce_model",
                "maximum_fill_deadline_months",
                239,
                "must remain 240",
            ),
            ("workforce_model", "max_penalty", -1, "cannot be negative"),
            ("workforce_model", "strategic_relief", 0, r"in \(0, 1\]"),
            ("native_input_fit", "default_priority", -1, "between 0 and 10"),
            ("native_input_fit", "maximum_priority", 9, "must remain 10"),
            ("native_input_fit", "max_bonus", -1, "cannot be negative"),
            ("native_input_fit", "shortage_discount", 2, "between 0 and 1"),
        )
        for section, key, value, message in cases:
            with self.subTest(section=section, key=key):
                raw = self._raw_rules()
                raw[section][key] = value
                with self.assertRaisesRegex(ValueError, message):
                    AutomationRules.from_mapping(raw)

    def test_rejects_invalid_building_priorities_and_groups(self):
        cases = (
            (
                lambda raw: raw["building_priorities"].update(overrides=[]),
                "must be a mapping",
            ),
            (
                lambda raw: raw["building_priorities"]["overrides"].update({"bad id": 1}),
                "script identifier",
            ),
            (
                lambda raw: raw["building_priorities"]["overrides"].update(granary=True),
                "must be numeric",
            ),
            (
                lambda raw: raw["building_priorities"]["overrides"].update(granary=11),
                "outside 0-10",
            ),
            (
                lambda raw: raw["building_priorities"].update(minimum=10, maximum=10),
                "minimum < maximum",
            ),
            (
                lambda raw: raw["building_priorities"].update(default=11),
                "outside the configured range",
            ),
            (
                lambda raw: raw["building_priorities"].update(score_per_point=0),
                "must be positive",
            ),
            (
                lambda raw: raw["goods_groups"].update({"bad group": []}),
                "script identifier",
            ),
            (
                lambda raw: raw["goods_groups"].update(food="wheat"),
                "list of script identifiers",
            ),
            (
                lambda raw: raw["goods_groups"].update(food=["bad id"]),
                "script identifier",
            ),
            (
                lambda raw: raw["goods_groups"]["food"].append("wheat"),
                "duplicate ids",
            ),
        )
        for mutate, message in cases:
            with self.subTest(message=message):
                raw = self._raw_rules()
                mutate(raw)
                with self.assertRaisesRegex(ValueError, message):
                    AutomationRules.from_mapping(raw)

    def test_rejects_invalid_rule_structure_and_file_root(self):
        raw = self._raw_rules()
        raw["schema_version"] = 6
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            AutomationRules.from_mapping(raw)

        raw = self._raw_rules()
        raw["goods_groups"].pop("food")
        with self.assertRaisesRegex(ValueError, "missing goods groups"):
            AutomationRules.from_mapping(raw)

        raw = self._raw_rules()
        raw["location_scores"] = []
        with self.assertRaisesRegex(ValueError, "must be a mapping"):
            AutomationRules.from_mapping(raw)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be a mapping"):
                load_automation_rules(path)


if __name__ == "__main__":
    unittest.main()
