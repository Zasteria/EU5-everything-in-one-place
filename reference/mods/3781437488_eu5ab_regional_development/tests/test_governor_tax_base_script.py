import unittest

from src.eu5autobuild.governor_generator import render_governor_script_values
from tests._governor_script_vm import GovernorScriptVM, parse


class TaxBaseVM(GovernorScriptVM):
    def __init__(self, tax_base, control):
        self.inputs = {"location_tax_base": tax_base, "local_control": control}

    def value(self, expression, stack):
        if isinstance(expression, str) and expression in self.inputs:
            return self.inputs[expression]
        if isinstance(expression, list):
            expanded = []
            for key, operator, body in expression:
                if key == "if":
                    limits = next(value for name, _, value in body if name == "limit")
                    if not all(op == ">" and self.value(name, stack) > float(value)
                               for name, op, value in limits):
                        continue
                    expanded.extend(entry for entry in body if entry[0] != "limit")
                else:
                    expanded.append((key, operator, body))
            expression = expanded
        return super().value(expression, stack)


class GovernorTaxBaseScriptTests(unittest.TestCase):
    def test_potential_tax_base_handles_zero_and_preserves_normal_control(self):
        definitions = {key: value for key, _, value in parse(render_governor_script_values())}
        expression = definitions["eu5ab_governor_potential_tax_base"]
        for tax_base, control, expected in (
            (0, 0, 0),
            (2, 0, 0),
            (2, 0.001, 2000),
            (2, 0.01, 200),
            (2, 0.05, 40),
            (2, 0.5, 4),
            (2, 1, 2),
        ):
            with self.subTest(tax_base=tax_base, control=control):
                self.assertAlmostEqual(TaxBaseVM(tax_base, control).value(expression, []), expected)
