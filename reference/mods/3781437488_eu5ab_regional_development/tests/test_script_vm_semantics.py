"""Prevent engine-invalid missing writes from passing runtime regressions."""
import unittest

from tests._governor_script_vm import GovernorScriptVM, parse


class ScriptVMSemanticsTests(unittest.TestCase):
    def test_missing_zero_and_scope_values_remain_distinct(self):
        vm = GovernorScriptVM({}, {}, {}, {}, (), (), None)
        stack = [vm.ROOT]
        increment = parse("change_variable = { name = counter add = 1 }")
        self.assertIsNone(vm.value("var:counter", stack))
        self.assertFalse(vm.test("var:counter", "=", "0", stack))
        with self.assertRaisesRegex(AssertionError, "unset counter"):
            vm.execute(increment, stack)
        self.assertNotIn("counter", vm.vars[vm.ROOT])
        vm.execute(parse("set_variable = { name = counter value = 0 }"), stack)
        self.assertTrue(vm.test("var:counter", "=", "0", stack))
        vm.execute(increment, stack)
        self.assertEqual(vm.vars[vm.ROOT]["counter"], 1)
        vm.execute(parse("set_variable = { name = counter value = this }"), stack)
        with self.assertRaisesRegex(AssertionError, "nonnumeric counter"):
            vm.execute(increment, stack)
