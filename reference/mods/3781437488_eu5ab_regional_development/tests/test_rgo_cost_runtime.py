"""Execute generated RGO gates/accounting with injected native transactions.

Five-decimal truncation is a calibration model, not proof of engine arithmetic.
The fake synchronous transaction tests our accounting, not engine timing.
"""

from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_FLOOR, ROUND_CEILING
import unittest

from tests._governor_script_vm import GovernorScriptVM, parse
from tests import _generated as automation


D = Decimal
UNIT = D("0.00001")
EFFECT = "eu5ab_try_construct_rgo_need"


class RgoVM(GovernorScriptVM):
    def __init__(self, effects, triggers, values):
        self.definitions = effects
        self.triggers, self.values = triggers, values
        self.local, self.scopes = {}, {"eu5ab_candidate_location": "a"}
        self.operations = 0
        self.vars = {self.ROOT: {
            'eu5ab_scan_year': D(1410), 'eu5ab_scan_month': D(5),
            "eu5ab_global_budget_remaining": D(1000),
            "eu5ab_global_min_cash_reserve": D(200),
            "eu5ab_constructions_started_this_tick": D(0),
            "eu5ab_monthly_build_quota": D(10),
            "eu5ab_global_allow_rgo": D(1),
            "eu5ab_global_enabled": D(1),
            "eu5ab_diag_active_mod_projects": D(0),
            "eu5ab_rgo_started_this_tick": D(0),
            "eu5ab_diag_fail_vanilla": D(0),
        }, "a": {}, "b": {}}
        self.lists = {s: {} for s in self.vars}
        self.owners = {"a": self.ROOT, "b": self.ROOT}
        self.gold, self.inflation = D(1000), D(0)
        self.modifiers = {m: D(0) for m in (
            "mining", "farming", "hunting", "gathering", "forestry"
        )}
        self.locations = {s: dict(method="mining", output_price=D(3), market=True,
                                  lumber=D(1), masonry=D(1), queue=D(0))
                          for s in self.owners}
        self.calls = []
        self.actual_paid, self.reject = D("75.43575"), False
        self.queries = 0
        self.day = 23  # Native transaction tests enter this month's firing window.

    def arithmetic(self, entries, stack, result=None):
        if result is None:
            result = D(0)
        matched = False
        for key, _, expression in entries:
            if key == "owner":
                result = self.arithmetic(expression, stack + [self.owners[stack[-1]]], result)
                continue
            if key in ("if", "else_if", "else"):
                if key == "if":
                    matched = False
                data = dict((k, v) for k, _, v in expression)
                if not matched and (key == "else" or self.condition(data["limit"], stack)):
                    result = self.arithmetic(
                        [e for e in expression if e[0] != "limit"], stack, result
                    )
                    matched = True
                continue
            operand = self.value(expression, stack)
            if key == "value":
                result = operand
            elif key == "add":
                result += operand
            elif key == "subtract":
                result -= operand
            elif key == "multiply":
                result *= operand
            elif key == "divide":
                result /= operand
            elif key == "min":
                result = max(result, operand)
            elif key == "max":
                result = min(result, operand)
            elif key == "floor":
                result = result.to_integral_value(rounding=ROUND_FLOOR)
            elif key == "ceiling":
                result = result.to_integral_value(rounding=ROUND_CEILING)
            else:
                raise AssertionError(key)
            result = D(result).quantize(UNIT, rounding=ROUND_DOWN)
        return result

    def value(self, x, stack):
        if isinstance(x, list):
            return self.arithmetic(x, stack)
        x = x.strip('"')
        if x in self.values:
            return self.arithmetic(self.values[x], stack)
        if x.startswith('owner.') and x[6:] in self.values:
            return self.value(x[6:], stack + [self.owners[stack[-1]]])
        if x in ("gold", "owner.gold"):
            return self.gold
        if x == "owner.inflation":
            return self.inflation
        if x.startswith("owner.modifier:expand_rgo_"):
            return self.modifiers[x.removeprefix("owner.modifier:expand_rgo_")
                                  .removesuffix("_cost_modifier")]
        constants = {
            "define:NMarket|MIN_PRICE_IMPACT": D("-.33"),
            "define:NMarket|MAX_PRICE_IMPACT": D(3),
            "define:NEconomy|GOODS_RGO_BASE_COST": D(".5"),
            "define:NEconomy|GOODS_RGO_PRICE_SCALE": D(".25"),
            "default_price(goods:lumber)": D(1),
            "default_price(goods:masonry)": D(1),
            "max_rgo_workers": D(4000),
        }
        if x in constants:
            return constants[x]
        if x == "default_price(raw_material)":
            return self.locations[stack[-1]]["output_price"]
        if x.startswith("market.market_price(goods:"):
            self.queries += 1
            return self.locations[stack[-1]][x.split(":")[1].removesuffix(")")]
        if x == "num_civil_constructions":
            return self.locations[stack[-1]]["queue"]
        try:
            return D(x)
        except InvalidOperation:
            return super().value(x, stack)

    def test(self, k, op, v, stack):
        if k == 'owner' and isinstance(v, list):
            return self.condition(v, stack + [self.owners[stack[-1]]])
        if k == 'has_variable_list':
            return bool(self.lists[stack[-1]].get(v))
        if k in self.triggers:
            if k in ("eu5ab_rgo_capacity_available", "eu5ab_rgo_location_available",
                     "eu5ab_rgo_utilization_allowed", "eu5ab_rgo_workforce_allowed",
                     "eu5ab_rgo_market_need_present", "eu5ab_rgo_price_allowed",
                     "eu5ab_rgo_score_allowed", "eu5ab_rgo_pending_allowed",
                     "eu5ab_location_template_not_paused"):
                return v == "yes"  # Orthogonal native/workforce gates are injected.
            return self.condition(self.triggers[k], stack) == (v == "yes")
        if k == "exists":
            return v != "market" or self.locations[stack[-1]]["market"]
        if k == "raw_material":
            return self.condition(v, stack)
        if k == "goods_method":
            return self.locations[stack[-1]]["method"] == v
        if k == "is_target_in_variable_list":
            data = dict((a, c) for a, _, c in v)
            return self.value(data["target"], stack) in self.lists[stack[-1]].get(data["name"], [])
        return super().test(k, op, v, stack)

    def execute(self, entries, stack):
        index = 0
        while index < len(entries):
            k, _, v = entries[index]
            end = index + 1
            if k == "if":
                while end < len(entries) and entries[end][0] in ("else_if", "else"):
                    end += 1
            if k == "owner":
                self.execute(v, stack + [self.owners[stack[-1]]])
            elif k == "construct_rgo_upgrade":
                self.calls.append(stack[-1])
                if not self.reject:
                    self.gold -= self.actual_paid
                    self.locations[stack[-1]]["queue"] += 1
            elif k == "eu5ab_record_rgo_start":
                # Pending output is exercised by the decision/ledger tests.
                self.vars[stack[-1]]["recorded_rgo_start"] = True
            elif k == "eu5ab_capture_rgo_start_output":
                pass  # Orthogonal output reads are exercised by the ledger tests.
            else:
                super().execute(entries[index:end], stack)
            index = end

    def attempt(self, location="a"):
        self.scopes["eu5ab_candidate_location"] = location
        self.execute(self.definitions[EFFECT], [location])

    def estimate(self, location="a"):
        return self.value("eu5ab_rgo_expansion_cost", [location])


class RgoCostRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        generated = automation.generated_fixture()
        cls.effects = dict((k, v) for k, _, v in parse(generated.effects))
        cls.triggers = dict((k, v) for k, _, v in parse(generated.triggers))
        cls.values = dict((k, v) for k, _, v in parse(generated.values))

    def vm(self):
        return RgoVM(self.effects, self.triggers, self.values)

    def test_swe_observed_paid_cost_calibration(self):
        vm = self.vm()
        vm.inflation = D(".00082")
        vm.modifiers["mining"] = D("-.1")
        vm.locations["a"]["lumber"] = D(".56666")  # .85 / 1.5; impact hits floor.
        self.assertEqual(vm.estimate(), D("75.43575"))
        self.assertLessEqual(vm.queries, 2)

    def test_each_category_uses_its_own_modifier_and_material(self):
        for method in ("mining", "farming", "hunting", "gathering", "forestry"):
            with self.subTest(method=method):
                vm = self.vm()
                vm.locations["a"].update(method=method, lumber=D(1), masonry=D(3))
                vm.modifiers[method] = D("-.2")
                self.assertEqual(vm.estimate(), D(200 if method == "forestry" else 100))

    def test_provisional_material_curve_and_native_impact_bounds(self):
        for ratio, expected in (("0", "83.75"), (".91", "112.5"),
                                ("1", "125"), ("3", "250"), ("20", "500")):
            with self.subTest(ratio=ratio):
                vm = self.vm()
                vm.locations["a"]["lumber"] = D(ratio)
                self.assertEqual(vm.estimate(), D(expected))

    def test_cash_floor_and_positive_budget_allow_last_project_overshoot(self):
        for cash, budget, allowed in (("325", "125", True),
                                      ("324.99999", "125", False),
                                      ("325", "124.99999", True),
                                      ("325", "0", False)):
            with self.subTest(cash=cash, budget=budget):
                vm = self.vm()
                vm.gold = D(cash)
                vm.vars[vm.ROOT]["eu5ab_global_budget_remaining"] = D(budget)
                vm.attempt()
                self.assertEqual(bool(vm.calls), allowed)

    def test_legacy_execution_still_checks_cash_for_increased_cost(self):
        vm = self.vm()
        vm.vars[vm.ROOT]["eu5ab_global_budget_remaining"] = D(150)
        self.assertEqual(vm.estimate(), D(125))
        vm.gold = D(400)
        vm.locations["a"]["lumber"] = D(3)
        vm.attempt()
        self.assertEqual(vm.calls, [])

    def test_unsupported_inputs_do_not_attempt_construction(self):
        for field, value in (("market", False), ("method", "unknown"), ("output_price", D(0))):
            vm = self.vm()
            vm.locations["a"][field] = value
            vm.attempt()
            self.assertEqual(vm.calls, [])
        vm = self.vm()
        vm.modifiers["mining"] = D(-1)
        vm.attempt()
        self.assertEqual(vm.calls, [])

    def test_actual_payment_not_quote_settles_budget_once(self):
        for actual in ("75.43575", "140.07", "0"):
            with self.subTest(actual=actual):
                vm = self.vm()
                vm.actual_paid = D(actual)
                vm.attempt()
                state = vm.vars[vm.ROOT]
                self.assertEqual(vm.gold, D(1000) - D(actual))
                self.assertEqual(state["eu5ab_global_budget_remaining"], D(1000) - D(actual))
                self.assertEqual(state["eu5ab_diag_last_build_location"], "a")
                self.assertEqual(state["eu5ab_diag_last_build_kind"], 1)
                self.assertEqual(state["eu5ab_constructions_started_this_tick"], 1)
                self.assertEqual(vm.local, {})

    def test_native_rejection_leaves_budget_and_counters_unchanged(self):
        vm = self.vm()
        vm.reject = True
        vm.attempt()
        state = vm.vars[vm.ROOT]
        self.assertEqual((vm.gold, state["eu5ab_global_budget_remaining"]), (D(1000), D(1000)))
        self.assertEqual(state["eu5ab_constructions_started_this_tick"], 0)
        self.assertEqual(state["eu5ab_diag_fail_vanilla"], 1)
        self.assertEqual(vm.local, {})

    def test_consecutive_transactions_do_not_reuse_cash_snapshot(self):
        vm = self.vm()
        vm.attempt("a")
        vm.actual_paid = D("140.07")
        vm.attempt("b")
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_global_budget_remaining"], D("784.49425"))
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_constructions_started_this_tick"], 2)
        self.assertEqual(vm.local, {})

    def test_negative_cash_movement_does_not_refund_budget(self):
        vm = self.vm()
        vm.actual_paid = D(-5)
        vm.attempt()
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_global_budget_remaining"], D(1000))
        self.assertEqual(vm.gold, D(1005))
        self.assertEqual(vm.vars[vm.ROOT]["eu5ab_constructions_started_this_tick"], 1)
        self.assertEqual(vm.local, {})


if __name__ == "__main__":
    unittest.main()
