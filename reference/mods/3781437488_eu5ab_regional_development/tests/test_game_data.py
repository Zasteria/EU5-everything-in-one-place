from pathlib import Path
import tempfile
import unittest

from src.eu5autobuild.game_data import (
    building_upgrades_as_json,
    construction_demands_as_json,
    extract_building_upgrades,
    extract_rgo_base_costs,
    extract_supported_construction_demands,
    extract_supported_recipes,
    extract_workforce_model,
    parse_paradox_script,
    recipes_as_json,
    registered_dlc_names,
    workforce_model_as_json,
)
from src.eu5autobuild.game_root import configured_game_root
from src.eu5autobuild.policy import BuildingCatalog, load_building_catalog


ROOT = Path(__file__).resolve().parents[1]
GAME_ROOT = configured_game_root()
HAS_INSTALLED_GAME = bool(
    GAME_ROOT is not None
    and (GAME_ROOT / "game" / "in_game" / "common").is_dir()
)


class ParadoxScriptParserTests(unittest.TestCase):
    def test_dlc_registration_uses_descriptor_identity_not_directory_or_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(registered_dlc_names(root), frozenset())
            dlc = root / 'game/dlc/D009_placeholder'
            dlc.mkdir(parents=True)
            self.assertEqual(registered_dlc_names(root), frozenset())
            (dlc / 'package.dlc.json').write_text(
                '{"name": "d009_across_the_pillars", "enabled": false}', encoding='utf-8-sig')
            self.assertEqual(registered_dlc_names(root), frozenset({'d009_across_the_pillars'}))

    def test_parser_preserves_list_atoms_and_repeated_keys(self):
        parsed = parse_paradox_script(
            """
            thing = {
                possible = { first second }
                produced = tools
                output = 1.1 # inline comment
            }
            """
        )
        self.assertEqual(parsed[0][0], "thing")
        self.assertEqual(parsed[0][1][0][1], [(None, "first"), (None, "second")])

    def test_parser_rejects_unbalanced_or_missing_values(self):
        cases = (
            ("}", "Unexpected closing brace"),
            ("thing =", "Missing value"),
            ("thing = { value = 1", "Unclosed block"),
        )
        for text, message in cases:
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, message):
                    parse_paradox_script(text)

    def test_extracts_all_rgo_base_costs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prices = root / "game" / "in_game" / "common" / "prices"
            prices.mkdir(parents=True)
            (prices / "prices.txt").write_text(
                "\n".join(
                    f"expand_rgo_{method} = {{ gold = 100 }}"
                    for method in ("mining", "farming", "hunting", "gathering", "forestry")
                ),
                encoding="utf-8",
            )
            self.assertEqual(set(extract_rgo_base_costs(root).values()), {100.0})

    def test_extracts_only_supported_default_recipe(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            common = root / "game" / "in_game" / "common"
            for folder in ("building_types", "production_methods", "goods"):
                (common / folder).mkdir(parents=True, exist_ok=True)
            (common / "goods" / "goods.txt").write_text(
                "iron = {}\ntools = {}\n", encoding="utf-8"
            )
            (common / "building_types" / "buildings.txt").write_text(
                """
                tools_workshop = {
                    possible_production_methods = { default_tools better_tools }
                }
                unsupported = {
                    possible_production_methods = { other }
                }
                """,
                encoding="utf-8",
            )
            (common / "production_methods" / "methods.txt").write_text(
                """
                default_tools = { iron = 0.8 produced = tools output = 1.0 }
                better_tools = { iron = 0.9 produced = tools output = 1.4 allow = { always = yes } }
                other = { produced = tools output = 99 }
                """,
                encoding="utf-8",
            )
            catalog = BuildingCatalog.from_mapping(
                {
                    "buildings": [
                        {
                            "id": "tools_workshop",
                            "output_goods": ["tools"],
                            "workforce_pop_types": ["burghers"],
                        }
                    ]
                }
            )
            recipes = extract_supported_recipes(root, catalog)
            self.assertEqual(set(recipes), {"tools_workshop"})
            self.assertEqual(recipes["tools_workshop"].production_method_id, "default_tools")
            self.assertEqual(recipes["tools_workshop"].inputs, {"iron": 0.8})
            self.assertEqual(recipes["tools_workshop"].raw_inputs, {"iron": 0.8})
            self.assertEqual(recipes["tools_workshop"].outputs, {"tools": 1.0})

            preferred = extract_supported_recipes(
                root, catalog, {"tools_workshop": "better_tools"}
            )
            self.assertEqual(preferred["tools_workshop"].production_method_id, "better_tools")
            self.assertTrue(preferred["tools_workshop"].has_allow)

    def test_recipe_extraction_handles_unique_empty_and_missing_buildings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            common = root / "game" / "in_game" / "common"
            for folder in ("building_types", "production_methods", "goods"):
                (common / folder).mkdir(parents=True, exist_ok=True)
            (common / "goods" / "goods.txt").write_text(
                "iron = {}\ntools = { category = produced }\n",
                encoding="utf-8",
            )
            (common / "building_types" / "buildings.txt").write_text(
                """
                unique_shop = {
                    unique_production_methods = {
                        local_method = {
                            iron = 1 produced = tools output = 2
                            potential = { always = yes }
                        }
                    }
                }
                empty_shop = {}
                uneconomic_shop = { possible_production_methods = { no_output } }
                """,
                encoding="utf-8",
            )
            (common / "production_methods" / "methods.txt").write_text(
                "no_output = { iron = 1 }\n",
                encoding="utf-8",
            )
            catalog = BuildingCatalog.from_mapping(
                {
                    "buildings": [
                        {"id": "unique_shop"},
                        {"id": "empty_shop"},
                        {"id": "uneconomic_shop"},
                        {"id": "missing_shop"},
                    ]
                }
            )

            recipes = extract_supported_recipes(root, catalog)

            self.assertEqual(set(recipes), {"unique_shop"})
            self.assertTrue(recipes["unique_shop"].has_potential)
            self.assertEqual(recipes["unique_shop"].raw_inputs, {"iron": 1.0})

    def test_extracts_transitive_supported_upgrade_destinations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            building_types = (
                root / "game" / "in_game" / "common" / "building_types"
            )
            building_types.mkdir(parents=True)
            (building_types / "chains.txt").write_text(
                """
                tools_guild = {}
                tools_workshop = { obsolete = tools_guild }
                iron_foundry = { obsolete = tools_workshop }
                paper_guild = {}
                paper_workshop = { obsolete = paper_guild }
                paper_manufactory = { obsolete = paper_workshop }
                paper_mill = { obsolete = paper_manufactory }
                """,
                encoding="utf-8",
            )
            catalog = BuildingCatalog.from_mapping(
                {
                    "buildings": [
                        {"id": "tools_guild"},
                        {"id": "tools_workshop"},
                        {"id": "iron_foundry"},
                        {"id": "paper_workshop"},
                        {"id": "paper_mill"},
                    ]
                }
            )

            upgrades = extract_building_upgrades(root, catalog)

            self.assertEqual(
                upgrades.successors["tools_guild"],
                ("iron_foundry", "tools_workshop"),
            )
            self.assertEqual(
                upgrades.successors["paper_workshop"],
                ("paper_mill",),
            )
            self.assertEqual(
                upgrades.predecessors["paper_mill"],
                ("paper_guild", "paper_manufactory", "paper_workshop"),
            )
            self.assertNotIn("paper_manufactory", upgrades.successors["paper_workshop"])
            self.assertEqual(upgrades.native_successors["paper_workshop"],
                             ("paper_manufactory", "paper_mill"))
            self.assertEqual(upgrades.native_successors["paper_guild"],
                             ("paper_manufactory", "paper_mill", "paper_workshop"))
            self.assertEqual(
                building_upgrades_as_json(upgrades),
                building_upgrades_as_json(extract_building_upgrades(root, catalog)),
            )

    def test_extracts_supported_construction_goods_from_vanilla_demand_bundle(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            common = root / "game" / "in_game" / "common"
            (common / "building_types").mkdir(parents=True)
            (common / "goods_demand").mkdir(parents=True)
            (common / "building_types" / "buildings.txt").write_text(
                """
                tools_workshop = { construction_demand = workshop_construction }
                missing_bundle = { construction_demand = missing_construction }
                """,
                encoding="utf-8",
            )
            (common / "goods_demand" / "construction.txt").write_text(
                """
                workshop_construction = {
                    masonry = 1
                    tools = 0.25
                    category = building_construction
                }
                """,
                encoding="utf-8",
            )
            catalog = BuildingCatalog.from_mapping(
                {
                    "buildings": [
                        {"id": "tools_workshop"},
                        {"id": "missing_bundle"},
                        {"id": "unsupported"},
                    ]
                }
            )

            demands = extract_supported_construction_demands(root, catalog)

            self.assertEqual(set(demands), {"tools_workshop"})
            self.assertEqual(demands["tools_workshop"].demand_id, "workshop_construction")
            self.assertEqual(
                demands["tools_workshop"].goods,
                {"masonry": 1.0, "tools": 0.25},
            )
            self.assertEqual(
                construction_demands_as_json(demands),
                construction_demands_as_json(
                    extract_supported_construction_demands(root, catalog)
                ),
            )

    def test_extracts_jobs_direct_promotion_paths_and_base_without_fake_monthly_api(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            common = root / "game" / "in_game" / "common"
            (common / "building_types").mkdir(parents=True)
            (common / "pop_types").mkdir(parents=True)
            values = (
                root
                / "game"
                / "main_menu"
                / "common"
                / "script_values"
            )
            values.mkdir(parents=True)
            static = (
                root
                / "game"
                / "main_menu"
                / "common"
                / "static_modifiers"
            )
            static.mkdir(parents=True)
            (common / "building_types" / "buildings.txt").write_text(
                """
                tools_workshop = {
                    pop_type = burghers
                    employment_size = workshop_employment
                }
                """,
                encoding="utf-8",
            )
            (common / "pop_types" / "pops.txt").write_text(
                """
                peasants = {
                    promote_to = burghers
                    promote_to = soldiers
                    promotion_factor = 0.5
                }
                burghers = { has_cap = yes promotion_factor = 0.5 }
                """,
                encoding="utf-8",
            )
            (values / "default_values.txt").write_text(
                "workshop_employment = 0.1\n",
                encoding="utf-8",
            )
            (static / "location.txt").write_text(
                """
                location_base_values = { local_pop_promotion_speed = 0.001 }
                rgo_level = { local_laborers_desired_pop = 1 }
                """,
                encoding="utf-8",
            )
            catalog = BuildingCatalog.from_mapping(
                {"buildings": [{"id": "tools_workshop"}]}
            )

            model = extract_workforce_model(root, catalog)

            self.assertEqual(model.buildings["tools_workshop"].jobs_per_level, 100)
            self.assertEqual(
                model.promotion_paths["peasants"].targets,
                ("burghers", "soldiers"),
            )
            self.assertTrue(model.promotion_paths["burghers"].has_cap)
            self.assertEqual(model.base_promotion_speed, 0.001)
            self.assertEqual(model.rgo_jobs_per_level, 1000)
            self.assertFalse(model.monthly_script_value_available)
            self.assertEqual(
                workforce_model_as_json(model),
                workforce_model_as_json(extract_workforce_model(root, catalog)),
            )

    def test_workforce_extraction_skips_incomplete_or_unresolved_jobs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            building_types = root / "game" / "in_game" / "common" / "building_types"
            pop_types = root / "game" / "in_game" / "common" / "pop_types"
            building_types.mkdir(parents=True)
            pop_types.mkdir(parents=True)
            (building_types / "buildings.txt").write_text(
                """
                missing_pop = { employment_size = 0.1 }
                missing_size = { pop_type = burghers }
                unresolved_size = { pop_type = burghers employment_size = unknown_size }
                """,
                encoding="utf-8",
            )
            catalog = BuildingCatalog.from_mapping(
                {
                    "buildings": [
                        {"id": "missing_pop"},
                        {"id": "missing_size"},
                        {"id": "unresolved_size"},
                    ]
                }
            )

            model = extract_workforce_model(root, catalog)

            self.assertEqual(model.buildings, {})
            self.assertEqual(model.all_buildings, {})
            self.assertIsNone(model.base_promotion_speed)


@unittest.skipUnless(
    HAS_INSTALLED_GAME,
    "Set EU5_GAME_ROOT to run installed-game integration tests",
)
class InstalledGameRecipeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if GAME_ROOT is None:
            raise RuntimeError("EU5 game root is required for installed-game data tests")
        cls.catalog = load_building_catalog(ROOT / "policies" / "building_catalog.json")
        cls.recipes = extract_supported_recipes(GAME_ROOT, cls.catalog)
        cls.construction_demands = extract_supported_construction_demands(
            GAME_ROOT, cls.catalog
        )
        cls.upgrades = extract_building_upgrades(GAME_ROOT, cls.catalog)
        cls.workforce = extract_workforce_model(GAME_ROOT, cls.catalog)
        cls.rgo_base_costs = extract_rgo_base_costs(GAME_ROOT)

    def test_known_supported_recipe_matches_game_data(self):
        recipe = self.recipes["tools_workshop"]
        self.assertEqual(recipe.production_method_id, "metalwork_workshop_maintenance")
        self.assertEqual(recipe.inputs, {"iron": 0.88})
        self.assertEqual(recipe.raw_inputs, {"iron": 0.88})
        self.assertEqual(recipe.outputs, {"tools": 1.1})

    def test_output_is_bounded_and_stable(self):
        self.assertLessEqual(len(self.recipes), len(self.catalog.buildings))
        first = recipes_as_json(self.recipes)
        second = recipes_as_json(extract_supported_recipes(GAME_ROOT, self.catalog))
        self.assertEqual(first, second)
        self.assertNotIn("unsupported", first)

    def test_known_upgrade_chain_matches_game_data(self):
        self.assertEqual(
            self.upgrades.successors["tools_guild"],
            ("iron_foundry", "iron_mill", "tools_workshop"),
        )
        self.assertIn("paper_manufactory", self.upgrades.predecessors["paper_mill"])

    def test_known_construction_demand_matches_game_data(self):
        demand = self.construction_demands["tools_workshop"]
        self.assertEqual(demand.demand_id, "workshop_construction")
        self.assertEqual(demand.goods, {"masonry": 1.0})

    def test_workforce_and_promotion_sources_match_installed_vanilla(self):
        self.assertEqual(len(self.workforce.buildings), len(self.catalog.buildings))
        self.assertEqual(
            self.workforce.buildings["tools_workshop"].jobs_per_level,
            100,
        )
        self.assertIn("burghers", self.workforce.promotion_paths["peasants"].targets)
        self.assertEqual(self.workforce.base_promotion_speed, 0.001)
        self.assertFalse(self.workforce.monthly_script_value_available)

    def test_rgo_base_costs_match_budget_rule(self):
        self.assertEqual(set(self.rgo_base_costs.values()), {100.0})


if __name__ == "__main__":
    unittest.main()
