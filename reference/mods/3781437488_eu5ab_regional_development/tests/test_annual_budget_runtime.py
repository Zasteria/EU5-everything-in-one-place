"""Exercise the emitted annual ledger and native-start confirmation boundary."""
from copy import deepcopy
import unittest

from tests._generated import generated_fixture
from tests.test_queue_recovery_runtime import QueueVM


class AnnualBudgetRuntimeTests(unittest.TestCase):
    def vm(self):
        fixture = generated_fixture()
        vm = QueueVM(fixture.effects, fixture.scripted_guis)
        vm.year = 1436
        vm.native['monthly_income_total'] = 1000
        vm.vars[vm.ROOT].update(eu5ab_global_budget_mode=1,
                                eu5ab_global_fixed_annual_budget=550000,
                                eu5ab_global_budget_limit=550000,
                                eu5ab_global_budget_remaining=527389.267)
        return vm

    def test_repeated_settings_and_load_keep_observed_spending(self):
        vm = self.vm()
        vm.run('eu5ab_ensure_annual_budget', vm.ROOT)
        country = vm.vars[vm.ROOT]
        self.assertAlmostEqual(country['eu5ab_global_budget_spent'], 22610.733)
        before = deepcopy(country)
        for _ in range(4):
            vm.run('eu5ab_refresh_global_budget', vm.ROOT)
            vm.run('eu5ab_ensure_annual_budget', vm.ROOT)
        self.assertEqual(country, before)
        restored = self.vm()
        restored.vars = deepcopy(vm.vars)
        restored.run('eu5ab_ensure_annual_budget', restored.ROOT)
        self.assertEqual(restored.vars[restored.ROOT], before)

    def test_zero_balance_missing_from_save_is_not_a_fresh_budget(self):
        vm = self.vm()
        country = vm.vars[vm.ROOT]
        country.pop('eu5ab_global_budget_remaining')
        vm.run('eu5ab_ensure_annual_budget', vm.ROOT)
        self.assertEqual(country['eu5ab_global_budget_spent'], 550000)
        country.pop('eu5ab_global_budget_remaining')  # Native saves omit zero.
        vm.run('eu5ab_refresh_global_budget', vm.ROOT)
        self.assertEqual(country['eu5ab_global_budget_remaining'], 0)
        self.assertEqual(country['eu5ab_budget_year'], 1436)

    def test_real_setting_changes_preserve_spent_even_after_lowering_limit(self):
        vm = self.vm()
        vm.run('eu5ab_ensure_annual_budget', vm.ROOT)
        country = vm.vars[vm.ROOT]
        country['eu5ab_global_fixed_annual_budget'] = 10000
        vm.run('eu5ab_refresh_global_budget', vm.ROOT)
        self.assertEqual(country['eu5ab_global_budget_remaining'], 0)
        country['eu5ab_global_fixed_annual_budget'] = 600000
        vm.run('eu5ab_refresh_global_budget', vm.ROOT)
        self.assertAlmostEqual(country['eu5ab_global_budget_remaining'], 577389.267)

    def test_income_changes_do_not_revalue_an_unchanged_setting_callback(self):
        vm = self.vm()
        country = vm.vars[vm.ROOT]
        country.update(eu5ab_global_budget_mode=3, eu5ab_global_budget_limit=6000,
                       eu5ab_global_budget_remaining=5000)
        vm.run('eu5ab_ensure_annual_budget', vm.ROOT)
        vm.native['monthly_income_total'] = 2000
        vm.run('eu5ab_refresh_global_budget', vm.ROOT)
        self.assertEqual(country['eu5ab_global_budget_limit'], 6000)
        country['eu5ab_global_budget_mode'] = 4
        vm.run('eu5ab_refresh_global_budget', vm.ROOT)
        self.assertEqual(country['eu5ab_global_budget_remaining'], 15000)

    def test_year_rollover_happens_once_and_does_not_grow_saved_history(self):
        vm = self.vm()
        vm.run('eu5ab_ensure_annual_budget', vm.ROOT)
        country = vm.vars[vm.ROOT]
        fields = set(country)
        for year in range(1437, 1447):
            vm.year = year
            vm.run('eu5ab_ensure_annual_budget', vm.ROOT)
            self.assertEqual(country['eu5ab_global_budget_remaining'], 550000)
            vm.local['eu5ab_budget_charge'] = 50
            vm.run('eu5ab_charge_annual_budget', vm.ROOT)
            vm.run('eu5ab_ensure_annual_budget', vm.ROOT)
            self.assertEqual(country['eu5ab_global_budget_remaining'], 549950)
            self.assertEqual(country['eu5ab_budget_year'], year)
            self.assertEqual(set(country), fields)

    def test_physical_start_confirmation_charges_once(self):
        vm = self.vm()
        country = vm.vars[vm.ROOT]
        country.update(eu5ab_q_planned_spend=100, eu5ab_q_planned_budget=100)
        vm.vars['location'].update(eu5ab_q_fire_issued=1, eu5ab_q_approved_cost=100,
                                   eu5ab_q_type_queue_before=0, eu5ab_q_type_level_before=0)
        vm.native['eu5ab_candidate_queued_levels'] = 1
        vm.run('eu5ab_confirm_engine_candidate')
        self.assertAlmostEqual(country['eu5ab_global_budget_remaining'], 527289.267)
        before = deepcopy((vm.vars, vm.lists, vm.variable_maps))
        vm.run('eu5ab_confirm_engine_candidate')
        self.assertEqual((vm.vars, vm.lists, vm.variable_maps), before)
        self.assertEqual(country['eu5ab_q_planned_spend'], 0)


if __name__ == '__main__':
    unittest.main()
