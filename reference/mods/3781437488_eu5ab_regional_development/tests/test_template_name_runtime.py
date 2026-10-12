"""Run generated name lifecycle effects; EU5 serialization/rendering need live tests."""

import json
import re
import unittest

from tests._governor_script_vm import GovernorScriptVM, parse
from tests import _generated as generator_tests


class TemplateNameVM(GovernorScriptVM):
    def __init__(self, definitions):
        super().__init__({}, {}, {}, {}, (), (), None)
        self.definitions = definitions
        self.maps = {}

    def value(self, value, stack):
        if isinstance(value, str):
            if value.startswith("building_type:"):
                return value
            match = re.fullmatch(r"variable_map\(([^|]+)\|([^)]*)\)", value)
            if match:
                return self.maps.get(stack[-1], {}).get(match[1], {}).get(match[2], 0)
        return super().value(value, stack)

    def test(self, key, operator, value, stack):
        if key == "always":
            return value == "yes"
        if key == "exists":
            return self.value(value, stack) is not None
        maps = self.maps.get(stack[-1], {})
        if key == "has_variable_map":
            return bool(maps.get(value))
        if key == "is_key_in_variable_map":
            data = {k: v for k, _, v in value}
            return self.value(data["target"], stack) in maps.get(data["name"], {})
        return super().test(key, operator, value, stack)

    def execute(self, entries, stack):
        # Preserve whole if/else chains when delegating to the shared VM.
        index = 0
        while index < len(entries):
            key, _, value = entries[index]
            end = index + 1
            if key == "if":
                while end < len(entries) and entries[end][0] in ("else_if", "else"):
                    end += 1
            if key in ("add_to_variable_map", "remove_from_variable_map"):
                data = {k: v for k, _, v in value}
                mapping = self.maps.setdefault(stack[-1], {}).setdefault(data["name"], {})
                map_key = self.value(data["key"], stack)
                if key == "add_to_variable_map":
                    mapping[map_key] = self.value(data["value"], stack)
                else:
                    mapping.pop(map_key, None)
            else:
                super().execute(entries[index:end], stack)
            index = end

    def run(self, name, *, country="country", name_input=None):
        self.vars.setdefault(country, {})
        self.scopes = {} if name_input is None else {"eu5ab_template_name_input": name_input}
        self.local = {}
        self.operations = 0
        body = self.definitions[name]
        if name.startswith("eu5ab_gui_"):
            gui = {k: v for k, _, v in body}
            if not self.condition(gui["is_valid"], [country]):
                return
            body = gui["effect"]
        self.execute(body, [country])
        self.scopes.clear()


class TemplateNameRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        files = generator_tests.generated_fixture().files
        effects = files[generator_tests.ROOT / "in_game/common/scripted_effects/eu5ab_scripted_effects.txt"]
        guis = files[generator_tests.ROOT / "in_game/common/scripted_guis/eu5ab_scripted_guis.txt"]
        names = [
            "eu5ab_load_blank_template_into_editor",
            "eu5ab_load_recommended_template_into_editor",
            "eu5ab_commit_active_template_editor",
            "eu5ab_select_first_player_template",
            "eu5ab_copy_template_slot_1_to_slot_2",
        ]
        names += [f"eu5ab_load_preset_{p.id}_into_editor" for p in generator_tests.generated_fixture().policies]
        for slot in range(1, 21):
            names += [
                f"eu5ab_template_slot_{slot}_ensure_defaults",
                f"eu5ab_load_template_slot_{slot}_into_editor",
                f"eu5ab_commit_template_editor_to_slot_{slot}",
                f"eu5ab_commit_template_editor_to_slot_{slot}_and_refresh_budget",
                f"eu5ab_gui_slot_{slot}_name_custom",
                f"eu5ab_gui_slot_{slot}_name_food_security",
                f"eu5ab_gui_delete_template_slot_{slot}",
                f"eu5ab_gui_copy_active_template_to_slot_{slot}",
            ]
        selected = "\n".join(
            generator_tests._blocks_for_token(effects + "\n" + guis, "\n" + name + " = ")[0]
            for name in names
        )
        selected = re.sub(r"saved_scopes = \{[^}]*\}", "", selected)
        cls.definitions = {k: v for k, _, v in parse(selected)}

    def vm(self):
        return TemplateNameVM(self.definitions)

    def test_rename_survives_later_rule_commits_and_discarded_gui_state(self):
        vm = self.vm()
        vm.run("eu5ab_load_template_slot_1_into_editor")
        vm.run("eu5ab_gui_slot_1_name_custom", name_input="江南 粮食-01")
        vm.run("eu5ab_commit_active_template_editor")
        # Restore only durable country state into a fresh VM. This exercises
        # generated script logic, not EU5's own save-file serializer.
        restored = self.vm()
        restored.vars = json.loads(json.dumps(vm.vars))
        restored.maps = json.loads(json.dumps(vm.maps))
        restored.run("eu5ab_load_template_slot_1_into_editor")
        restored.run("eu5ab_commit_active_template_editor")
        self.assertEqual(restored.vars[vm.ROOT]["eu5ab_tpl_1_custom_name"], "江南 粮食-01")
        self.assertEqual(restored.vars[vm.ROOT]["eu5ab_edit_custom_name"], "江南 粮食-01")

    def test_copy_carries_name_then_renaming_copy_leaves_source_unchanged(self):
        vm = self.vm()
        vm.run("eu5ab_gui_slot_1_name_custom", name_input="北方矿业")
        vm.run("eu5ab_copy_template_slot_1_to_slot_2")
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_tpl_2_custom_name"], "北方矿业")
        vm.run("eu5ab_gui_slot_2_name_custom", name_input="南方矿业")
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_tpl_1_custom_name"], "北方矿业")
        vm.run("eu5ab_gui_copy_active_template_to_slot_20")
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_tpl_20_custom_name"], "南方矿业")

    def test_old_save_without_name_clears_editor_and_overwritten_destination(self):
        vm = self.vm()
        vm.run("eu5ab_gui_slot_2_name_custom", name_input="不得残留")
        vm.run("eu5ab_copy_template_slot_1_to_slot_2")
        self.assertNotIn("eu5ab_edit_custom_name", vm.vars[vm.ROOT])
        self.assertNotIn("eu5ab_tpl_2_custom_name", vm.vars[vm.ROOT])
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_tpl_2_name_selected"], 0)

    def test_blank_recommended_and_presets_clear_previous_name(self):
        loaders = ["eu5ab_load_blank_template_into_editor", "eu5ab_load_recommended_template_into_editor"]
        loaders += [f"eu5ab_load_preset_{p.id}_into_editor" for p in generator_tests.generated_fixture().policies]
        for loader in loaders:
            with self.subTest(loader=loader):
                vm = self.vm()
                vm.run("eu5ab_gui_slot_1_name_custom", name_input="旧名称")
                vm.run(loader)
                vm.run("eu5ab_commit_template_editor_to_slot_1")
                self.assertNotIn("eu5ab_edit_custom_name", vm.vars[vm.ROOT])
                self.assertNotIn("eu5ab_tpl_1_custom_name", vm.vars[vm.ROOT])

    def test_delete_clears_name_before_slot_reuse(self):
        vm = self.vm()
        vm.run("eu5ab_load_template_slot_1_into_editor")
        vm.run("eu5ab_gui_slot_1_name_custom", name_input="删除后不复活")
        vm.run("eu5ab_gui_delete_template_slot_1")
        self.assertNotIn("eu5ab_tpl_1_custom_name", vm.vars[vm.ROOT])
        self.assertNotIn("eu5ab_tpl_1_exists", vm.vars[vm.ROOT])
        vm.run("eu5ab_load_recommended_template_into_editor")
        vm.run("eu5ab_commit_template_editor_to_slot_1")
        self.assertNotIn("eu5ab_tpl_1_custom_name", vm.vars[vm.ROOT])

    def test_same_slot_in_different_countries_has_independent_names(self):
        vm = self.vm()
        vm.run("eu5ab_gui_slot_1_name_custom", name_input="中国")
        vm.run("eu5ab_gui_slot_1_name_custom", country="other", name_input="France")
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_tpl_1_custom_name"], "中国")
        self.assertEqual(vm.vars["other"]["eu5ab_tpl_1_custom_name"], "France")

    def test_missing_input_scope_cannot_erase_name_and_builtin_choice_clears_it(self):
        vm = self.vm()
        vm.run("eu5ab_gui_slot_1_name_custom", name_input="保留")
        vm.run("eu5ab_gui_slot_1_name_custom")
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_tpl_1_custom_name"], "保留")
        vm.run("eu5ab_gui_slot_1_name_food_security")
        self.assertNotIn("eu5ab_tpl_1_custom_name", vm.vars[vm.ROOT])
        self.assertNotIn("eu5ab_edit_custom_name", vm.vars[vm.ROOT])


if __name__ == "__main__":
    unittest.main()
