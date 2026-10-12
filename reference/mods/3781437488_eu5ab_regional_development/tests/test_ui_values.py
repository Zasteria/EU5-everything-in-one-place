import unittest

from src.eu5autobuild.ui_values import (
    UI_NUMERIC_VARIABLES, bind_ui_values, render_ui_script_values,
)
from tests._governor_script_vm import GovernorScriptVM, parse


class UIValueVM(GovernorScriptVM):
    def test(self, key, op, value, stack):
        if key == "exists":
            return self.value(value, stack) is not None
        return super().test(key, op, value, stack)

    def value(self, value, stack):
        if isinstance(value, list):
            expanded = []
            for key, op, body in value:
                if key == "if":
                    condition = next(v for k, _, v in body if k == "limit")
                    if self.condition(condition, stack):
                        expanded.extend(item for item in body if item[0] != "limit")
                else:
                    expanded.append((key, op, body))
            return super().value(expanded, stack)
        return super().value(value, stack)


class UIValueTests(unittest.TestCase):
    def setUp(self):
        self.vm = UIValueVM({}, {}, {}, {}, (), (), None)
        self.definitions = {k: v for k, _, v in parse(render_ui_script_values())}

    def read(self, name):
        return self.vm.value(self.definitions[name + "_ui"], [self.vm.ROOT])

    def test_reports_before_first_run_default_to_zero_without_creating_state(self):
        before = dict(self.vm.vars[self.vm.ROOT])
        for name in UI_NUMERIC_VARIABLES:
            self.assertEqual(self.read(name), 0, name)
        self.assertEqual(self.vm.vars[self.vm.ROOT], before)

    def test_report_values_preserve_negative_profit_and_fractional_scores(self):
        for name in UI_NUMERIC_VARIABLES:
            if name == "eu5ab_diag_last_build_kind":
                continue
            for value in (-12.75, 0, 1410):
                self.vm.vars[self.vm.ROOT][name] = value
                self.assertEqual(self.read(name), value, name)

    def test_missing_last_project_targets_hide_result_but_rgo_needs_no_building(self):
        state = self.vm.vars[self.vm.ROOT]
        name = "eu5ab_diag_last_build_kind"
        state[name] = 3
        self.assertEqual(self.read(name), 0)
        state["eu5ab_diag_last_build_location"] = "location"
        self.assertEqual(self.read(name), 0)
        state["eu5ab_diag_last_building"] = "building"
        self.assertEqual(self.read(name), 3)
        del state["eu5ab_diag_last_building"]
        state[name] = 1
        self.assertEqual(self.read(name), 1)

    def test_binding_keeps_scope_objects_and_localization_precision(self):
        text = "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_last_actual_profit').GetValue|+=2]"
        bound = bind_ui_values(text)
        self.assertEqual(bound, "[GetPlayer.MakeScope.ScriptValue('eu5ab_diag_last_actual_profit_ui')|+=2]")
        scope = "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_last_build_location').GetLocation.GetName]"
        self.assertEqual(bind_ui_values(scope), scope)
        self.assertEqual(bind_ui_values(bound), bound)
