"""Focused tests for update evidence, policy coverage and safe mutation."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.eu5autobuild import game_update as update


class GameUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="eu5ab-update-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / "steamapps/common/EU5"
        self.cmf = self.root / "cmf"
        self.repo = self.root / "repo"
        self.config = {"schema_version": 1, "mechanic_sources": {
            "constants": {"patterns": ["game/main_menu/common/script_values/*.txt"],
                          "consumers": ["game_data.py"], "note": "Review constants"}},
            "cmf_patterns": ["in_game/common/scripted_effects/*.txt"],
            "cmf_required_symbols": ["cmm_register_bool_setting"],
            "building_decisions": {}, "generic_goods": {}, "open_adaptations": []}
        files = {
            "game/in_game/common/industry_types/main.txt": "food = { goods = { flour } }",
            "game/in_game/common/building_types/main.txt":
                "mill = { employment_size = jobs pop_type = peasants construction_demand = build "
                "possible_production_methods = { milling } allow = { population > 10 } }",
            "game/in_game/common/production_methods/main.txt":
                "milling = { wheat = 1 produced = flour output = 2 }",
            "game/in_game/common/goods/main.txt":
                "wheat = { method = farming } flour = { category = produced }",
            "game/in_game/common/goods_demand/main.txt": "build = { wheat = 2 }",
            "game/in_game/common/advances/main.txt":
                "early_mill = { age = age_3_discovery unlock_building = mill }",
            "game/main_menu/common/script_values/default_values.txt": "jobs = 0.16",
            "game/in_game/common/pop_types/main.txt": "peasants = { promote_to = burghers }",
            "game/main_menu/common/static_modifiers/main.txt":
                "location_base_values = { local_pop_promotion_speed = 1 } rgo_level = { local_laborers_desired_pop = 1 }",
            "game/in_game/common/prices/main.txt": "\n".join(
                f"{name} = {{ gold = 100 }}" for name in update.gd.RGO_EXPANSION_PRICE_IDS),
            "game/in_game/map_data/adjacencies.csv": "From;To;Type\na;b;sea\na;c;canal\n",
        }
        for relative, content in files.items():
            self.write(self.game / relative, content)
        self.write(self.game.parent.parent / "appmanifest_3450310.acf",
                   '"installdir" "EU5" "buildid" "123" "BetaKey" "1.4-beta" "LastOwner" "private"')
        self.write_json(self.cmf / ".metadata/metadata.json",
                        {"id": "community_mod_framework", "version": "2.5.0"})
        self.write(self.cmf / "in_game/common/scripted_effects/api.txt",
                   "cmm_register_bool_setting = { foo = yes }")
        self.write_json(self.repo / "policies/templates.json", {"policies": []})
        self.write_json(self.repo / "policies/video_building_priorities.json", {"manual_overrides": {}})
        self.write_json(self.repo / "policies/automation_rules.json",
                        {"goods_groups": {"food": ["wheat"]}, "building_groups": {},
                         "building_priorities": {"overrides": {"mill": 1}}})

    def write(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def write_json(self, path, content):
        self.write(path, json.dumps(content))

    def snapshot(self):
        return update.collect_snapshot(self.game, self.cmf, "1.4-beta", self.config)

    def test_snapshot_extracts_models_and_only_public_identity(self):
        snapshot = self.snapshot()
        data = snapshot["data"]
        self.assertEqual(data["raw_goods"], ["wheat"])
        self.assertEqual(data["workforce"]["buildings"][0]["jobs_per_level"], 160)
        self.assertEqual(data["unlock_ages"], {"mill": 3})
        self.assertEqual(data["straits"], {"a": ["b"], "b": ["a"]})
        self.assertEqual(snapshot["identity"]["steam"], {"buildid": "123", "BetaKey": "1.4-beta"})
        self.assertNotIn("private", json.dumps(snapshot))
        self.assertEqual(snapshot["diagnostics"], [])

    def test_comparison_operator_and_unknown_field_changes_survive_numeric_parser(self):
        before = self.snapshot()
        path = self.game / "game/in_game/common/building_types/main.txt"
        original = path.read_text()
        self.write(path, original.replace("population > 10", "population >= 10 future_rule = yes"))
        after = self.snapshot()
        changes = update.snapshot_diff(before, after)
        self.assertIn("mill", changes["building_definitions"]["changed"])
        self.assertNotIn("catalog", changes)
        self.assertNotIn("workforce", changes)
        self.assertEqual(update.snapshot_diff(None, after), {})
        self.assertEqual(update.normalized_script('x = "# text" # comment\ny >= 2'), 'x = "# text" y >= 2')

    def test_recipe_and_workforce_updates_report_old_and_new_values(self):
        before = self.snapshot()
        self.write(self.game / "game/main_menu/common/script_values/default_values.txt", "jobs = 0.2")
        self.write(self.game / "game/in_game/common/production_methods/main.txt",
                   "milling = { wheat = 2 produced = flour output = 3 }")
        changes = update.snapshot_diff(before, self.snapshot())
        self.assertIn("mill", changes["production"]["changed"])
        jobs = next(row for row in changes["workforce"]["changed"]["mill"] if row["field"] == "jobs_per_level")
        self.assertEqual((jobs["before"], jobs["after"]), (160, 200))

    def test_unresolved_workforce_and_missing_cmf_symbol_are_visible(self):
        self.write(self.game / "game/main_menu/common/script_values/default_values.txt", "jobs = unknown")
        self.write(self.cmf / "in_game/common/scripted_effects/api.txt", "renamed = { }")
        diagnostics = self.snapshot()["diagnostics"]
        self.assertIn("Unresolved workforce: mill", diagnostics)
        self.assertIn("Missing CMF definition: cmm_register_bool_setting", diagnostics)

    def test_policy_omissions_and_pending_work_survive_baseline_acceptance(self):
        before = self.snapshot()
        after = copy.deepcopy(before)
        after["data"]["catalog"]["buildings"].append({"id": "new_building"})
        self.config["building_decisions"] = {"mill": {"status": "pending", "reason": "Review flavor"}}
        self.config["open_adaptations"] = [{"id": "industry", "reason": "Implement new area system"}]
        path = self.repo / "policies/automation_rules.json"
        rules = update.read_json(path)
        rules["building_groups"] = {"food": ["removed_building"]}
        self.write_json(path, rules)
        issues = update.policy_issues(after, before, self.config, self.repo)
        self.assertTrue(any(item["subject"] == "new_building" for item in issues))
        self.assertTrue(any(item["kind"] == "stale_reference" for item in issues))
        after_accept = update.policy_issues(after, after, self.config, self.repo)
        self.assertTrue(any(item["subject"] == "mill" for item in after_accept))
        self.assertTrue(any(item["subject"] == "industry" for item in after_accept))

    def test_baseline_archives_previous_and_refuses_schema_drift(self):
        first = self.snapshot()
        path = self.root / "state/baseline.json"
        self.assertTrue(update.accept_baseline(first, path))
        self.assertFalse(update.accept_baseline(first, path))
        second = copy.deepcopy(first)
        second["identity"]["steam"]["buildid"] = "456"
        update.accept_baseline(second, path)
        history = list((path.parent / "history").glob("*.json"))
        self.assertEqual(len(history), 1)
        self.assertEqual(update.read_json(history[0]), first)
        second["extractor_version"] = 999
        self.write_json(path, second)
        with self.assertRaisesRegex(ValueError, "schema/extractor"):
            update.accept_baseline(first, path)
        self.assertEqual(update.read_json(path), second)

    def test_sync_rolls_back_written_files_on_failure(self):
        a, b = self.repo / "a.txt", self.repo / "b.txt"
        self.write(a, "old a")
        self.write(b, "old b")
        writer = update.atomic_write

        def fail_second(path, content):
            if path == b:
                raise OSError("injected write failure")
            writer(path, content)

        with patch.object(update, "ROOT", self.repo), patch.object(update, "atomic_write", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "injected"):
                update.apply_files({a: "new a", b: "new b"})
        self.assertEqual(a.read_text(), "old a")
        self.assertEqual(b.read_text(), "old b")

    def test_raw_goods_sync_has_no_bom_and_render_override_is_restored(self):
        path = self.repo / "raw.json"
        original = update.rgo_automation.RAW_GOODS_FILE
        with update.candidate_raw_goods(["camels"]):
            self.assertEqual(update.rgo_automation.raw_goods(), ("camels",))
        self.assertEqual(update.rgo_automation.RAW_GOODS_FILE, original)
        with patch.object(update, "ROOT", self.repo), patch.object(update.cb, "RAW_GOODS_FILE", path):
            update.apply_files({path: '["camels"]\n'})
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), ["camels"])

    def test_audit_does_not_change_baseline_and_check_returns_pending_status(self):
        snapshot = self.snapshot()
        baseline = self.root / "state/baseline.json"
        update.accept_baseline(snapshot, baseline)
        old = baseline.read_bytes()
        config = self.root / "config.json"
        self.write_json(config, self.config)
        args = ["--game-root", str(self.game), "--cmf-root", str(self.cmf),
                "--game-version", "1.4-beta", "--baseline", str(baseline),
                "--output", str(self.root / "report"), "--config", str(config)]
        issue = {"kind": "functional_adaptation", "subject": "industry", "detail": "Pending"}
        with patch.object(update, "policy_issues", return_value=[issue]), patch.object(update, "data_drift", return_value=[]), patch.object(update, "render_candidate", return_value={}):
            self.assertEqual(update.main(["audit", *args]), 0)
            self.assertEqual(update.main(["check", *args]), 1)
        self.assertEqual(baseline.read_bytes(), old)


if __name__ == "__main__":
    unittest.main()
