"""Execute the generated ledger, allowance and start/release lifecycle.

Native inputs are injected. Save/restore below checks our persistent records,
not the engine's serialization or native construction timing.
"""

from copy import deepcopy
from decimal import Decimal as D
import unittest

from src.eu5autobuild.rgo_pending import pending_factor
from tests import _generated as automation
from tests._governor_script_vm import parse
from tests.test_rgo_decision_runtime import RgoDecisionVM


class RgoPendingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        f = automation.generated_fixture()
        cls.effects = {k: v for k, _, v in parse(f.effects)}
        cls.triggers = {k: v for k, _, v in parse(f.triggers)}
        cls.values = {k: v for k, _, v in parse(f.values)}

    def setUp(self):
        self.vm = RgoDecisionVM(self.effects, self.triggers, self.values)

    def pending(self, location='b'):
        return self.vm.number('eu5ab_rgo_market_pending_quantity', location)

    def test_summary_survives_either_effect_min_convention_and_floors_debits(self):
        vm = self.vm
        execute = vm.execute

        def effect_min(entries, stack):
            for k, _, data in entries:
                if k == 'change_local_variable' and isinstance(data, list):
                    fields = {a: c for a, _, c in data}
                    if 'min' in fields:
                        old = vm.local.get(fields['name'], D(0))
                        vm.local[fields['name']] = min(old, vm.value(fields['min'], stack))
                        return
            execute(entries, stack)

        vm.execute = effect_min
        vm.locations['a']['output'] = D('5.21568')
        vm.attempt('a')
        vm.attempt('b')
        self.assertEqual(self.pending(), D('2.80392'))
        vm.refresh()
        self.assertEqual(self.pending(), D('2.80392'))
        # A stale/empty country map must not turn a debit into negative supply.
        vm.maps['country']['eu5ab_rgo_pending_output_iron'] = {}
        vm.execute(vm.definitions['eu5ab_remove_rgo_pending_summary'], ['a'])
        self.assertEqual(self.pending(), 0)

    def test_lost_marker_recovery_requires_unfinished_confirmed_record(self):
        for state, recover in (('unfinished', True), ('completed', False),
                               ('mixed', False), ('foreign', False), ('unknown', False)):
            with self.subTest(state=state):
                vm = RgoDecisionVM(self.effects, self.triggers, self.values)
                vm.attempt()
                vm.vars['a'].pop('eu5ab_active_rgo_construction')
                vm.lists['country']['eu5ab_active_project_locations'] = []
                if state == 'completed': vm.locations['a'].update(queue=D(0), levels=D(5))
                if state == 'mixed': vm.locations['a']['queue'] = D(2)
                if state == 'foreign': vm.owners['a'] = 'foreign'
                if state == 'unknown': vm.locations['a']['queue'] = D(-1)
                vm.refresh()
                self.assertEqual('eu5ab_active_rgo_construction' in vm.vars['a'], recover)
                self.assertEqual('a' in vm.lists['country']['eu5ab_active_project_locations'], recover)

    def test_empty_registry_never_reads_locations_or_adopts_manual_work(self):
        vm = self.vm
        vm.locations['a'].update(queue=D(3), levels=D(9), workers=D(1), output=D(0))
        vm.vars['a']['eu5ab_rgo_pending_quantity'] = D(999)
        reads = []
        execute = vm.execute

        def watched(entries, stack):
            reads.extend(stack[-1] for k, _, _ in entries if k == 'eu5ab_reconcile_rgo_pending_location')
            self.assertFalse(any(k == 'every_owned_location' for k, _, _ in entries))
            return execute(entries, stack)

        vm.execute = watched
        vm.refresh()
        self.assertEqual(reads, [])
        self.assertEqual(self.pending(), 0)
        self.assertEqual(vm.number('eu5ab_rgo_market_pending_unknown', 'b'), 0)
        self.assertNotIn('eu5ab_rgo_pending_locations', vm.lists['country'])
        vm.attempt('b')
        vm.locations['b']['paused'] = True
        vm.refresh()
        self.assertEqual(reads, ['b', 'b'])
        self.assertEqual(self.pending(), D('1.5'))

    def test_resource_change_clears_record_without_crediting_new_good(self):
        vm = self.vm
        vm.attempt()
        vm.locations['a']['good'] = 'silver'
        vm.refresh()
        self.assertEqual(self.pending(), 0)
        self.assertEqual(self.pending('a'), 0)
        self.assertNotIn('eu5ab_rgo_pending_good', vm.vars['a'])
        self.assertEqual(vm.lists['country']['eu5ab_rgo_pending_locations'], [])

    def test_ordinary_supply_and_confirmed_inputs_change_the_same_rgo_allowance(self):
        vm = self.vm
        vm.markets['m1'].update(demand=D(100), supply=D(100))
        vm.maps['country']['eu5ab_build_pending_iron'] = {'m1': D(3)}
        vm.maps['country']['eu5ab_build_future_input_iron'] = {'m1': D(5)}
        self.assertEqual(self.pending(), 3)
        self.assertEqual(vm.number('eu5ab_rgo_pending_limit', 'b'), D('15.5'))
        self.assertAlmostEqual(float(vm.number('eu5ab_rgo_pending_factor', 'b')),
                               pending_factor(3, 105, 100), places=4)
        vm.maps['country']['eu5ab_build_pending_unknown_iron'] = {'m1': D(1)}
        # An old building ledger has no live producer in the cohort model.
        self.assertTrue(vm.allowed('eu5ab_rgo_pending_allowed', 'b'))
        vm.maps['country']['eu5ab_rgo_pending_unknown_iron'] = {'m1': D(1)}
        self.assertFalse(vm.allowed('eu5ab_rgo_pending_allowed', 'b'))

    def test_generated_curve_and_explicit_admission(self):
        vm = self.vm
        for demand, supply in ((100, 200), (100, 95), (100, 0), (0, 0)):
            vm.markets['m1'].update(demand=D(demand), supply=D(supply))
            for pending in (0, 1, 2.5, 5, 7.5, 9.99999, 10, 15, 50, 110):
                vm.maps['country']['eu5ab_rgo_pending_output_iron'] = {'m1': D(str(pending))}
                expected = pending_factor(pending, demand, supply)
                self.assertAlmostEqual(float(vm.number('eu5ab_rgo_pending_factor')), expected, places=4)
                self.assertEqual(vm.allowed('eu5ab_rgo_pending_allowed'), expected > 0)
        for values in ((-1, 100, 200), (0, -1, 0), (0, 1, -1), (float('nan'), 1, 1)):
            self.assertEqual(pending_factor(*values), 0)

    def test_snapshot_survives_completion_partial_staffing_and_months(self):
        vm = self.vm
        vm.locations['a']['output'] = D('7.24')  # Four fully staffed levels at 1.81.
        vm.attempt('a')
        self.assertEqual(self.pending(), D('1.81'))
        self.assertNotIn('eu5ab_rgo_start_output', vm.vars['a'])
        vm.locations['a'].update(queue=D(0), levels=D(5), workers=D('4.9'), output=D('6.7'))
        vm.refresh()
        vm.advance(1200)
        vm.refresh()
        self.assertEqual(self.pending(), D('1.81'))
        vm.locations['a']['workers'] = D(5)
        vm.refresh()
        self.assertEqual(self.pending(), 0)
        self.assertNotIn('eu5ab_rgo_pending_unit_output', vm.vars['a'])

    def test_existing_staff_cannot_release_queued_projects(self):
        vm = self.vm
        vm.attempt()
        vm.refresh()
        self.assertEqual(self.pending(), D('1.5'))
        self.assertEqual(vm.vars['a']['eu5ab_rgo_pending_levels'], 1)

    def test_manual_additions_and_cancellations_remain_bounded_unknown(self):
        vm = self.vm
        vm.attempt()
        vm.locations['a']['queue'] = D(3)
        vm.refresh()
        self.assertEqual(self.pending(), 0)
        self.assertEqual(vm.number('eu5ab_rgo_market_pending_unknown', 'b'), 1)
        self.assertEqual(vm.vars['a']['eu5ab_rgo_pending_levels'], 1)
        vm.locations['a']['queue'] = D(1)
        vm.refresh()
        self.assertEqual(vm.number('eu5ab_rgo_market_pending_unknown', 'b'), 1)
        vm.locations['a'].update(queue=D(0), levels=D(5), workers=D('4.8'))
        vm.refresh()
        self.assertEqual(vm.vars['a']['eu5ab_rgo_pending_levels'], 1)
        vm.locations['a']['workers'] = D(5)
        vm.refresh()
        self.assertEqual(vm.lists['country']['eu5ab_rgo_pending_locations'], [])

    def test_released_record_never_reopens_after_unemployment(self):
        vm = self.vm
        vm.attempt()
        vm.locations['a'].update(queue=D(0), levels=D(5), workers=D(5))
        vm.refresh()
        self.assertEqual(vm.lists['country']['eu5ab_rgo_pending_locations'], [])
        vm.locations['a'].update(workers=D(0), output=D(0), queue=D(10))
        vm.refresh()
        self.assertEqual(self.pending(), 0)
        self.assertEqual(vm.number('eu5ab_rgo_market_pending_unknown', 'b'), 0)

    def test_level_loss_does_not_claim_to_identify_the_destroyed_project(self):
        vm = self.vm
        vm.attempt()
        vm.locations['a'].update(levels=D(3), queue=D(1), workers=D(2))
        vm.refresh()
        self.assertEqual(vm.vars['a']['eu5ab_rgo_pending_levels'], 1)
        self.assertEqual(vm.number('eu5ab_rgo_market_pending_unknown', 'b'), 1)
        vm.locations['a'].update(levels=D(4), queue=D(0), workers=D(3))
        vm.refresh()
        self.assertEqual(vm.number('eu5ab_rgo_market_pending_unknown', 'b'), 1)
        vm.locations['a']['workers'] = D(4)
        vm.refresh()
        self.assertEqual(vm.lists['country']['eu5ab_rgo_pending_locations'], [])

    def test_second_confirmed_start_keeps_only_mod_count_and_no_double_summary(self):
        vm = self.vm
        vm.attempt()
        # Inject a second successful native command with the first still queued.
        vm.execute(vm.definitions['eu5ab_capture_rgo_start_output'], ['a'])
        vm.locations['a']['queue'] += 1
        vm.execute(vm.definitions['eu5ab_record_rgo_start'], ['a'])
        self.assertEqual(vm.vars['a']['eu5ab_rgo_pending_levels'], 2)
        self.assertEqual(vm.lists['country']['eu5ab_rgo_pending_locations'], ['a'])
        self.assertEqual(self.pending(), 3)
        self.assertEqual(vm.number('eu5ab_rgo_market_pending_unknown', 'b'), 0)
        vm.locations['a'].update(queue=D(1), levels=D(5), workers=D(5))
        vm.refresh()
        self.assertEqual(vm.vars['a']['eu5ab_rgo_pending_levels'], 1)
        self.assertEqual(self.pending(), D('1.5'))
        vm.locations['a']['workers'] = D(4)
        vm.locations['a']['queue'] = D(20)
        vm.refresh()
        self.assertEqual(vm.vars['a']['eu5ab_rgo_pending_levels'], 1)
        self.assertEqual(vm.number('eu5ab_rgo_market_pending_unknown', 'b'), 1)

    def test_last_level_can_cross_allowance_and_later_starts_stop(self):
        vm = self.vm
        vm.locations['a']['output'] = D(36)
        vm.attempt()
        vm.locations['b']['output'] = D('7.24')
        vm.refresh()
        self.assertEqual(self.pending(), D(9))
        self.assertTrue(vm.allowed('eu5ab_rgo_expansion_allowed', 'b'))
        vm.attempt('b')
        self.assertEqual(self.pending(), D('10.81'))
        vm.attempt('c')
        self.assertEqual(vm.calls, ['a', 'b'])
        self.assertEqual(vm.locations['a']['queue'], 1)
        self.assertEqual(vm.locations['b']['queue'], 1)

    def test_zero_demand_allows_only_first_otherwise_eligible_level(self):
        vm = self.vm
        vm.markets['m1'].update(demand=D(0), supply=D(0))
        vm.locations['a']['workers'] = D(3)
        self.assertFalse(vm.allowed('eu5ab_rgo_expansion_allowed', 'a'))
        vm.attempt('b')
        vm.attempt('c')
        self.assertEqual(vm.calls, ['b'])
        self.assertEqual(self.pending(), D('1.5'))

    def test_failed_start_does_not_reserve_any_output(self):
        vm = self.vm
        vm.reject = True
        vm.attempt()
        self.assertEqual(self.pending(), 0)
        self.assertNotIn('eu5ab_rgo_pending_unit_output', vm.vars['a'])
        self.assertNotIn('eu5ab_rgo_start_output', vm.vars['a'])
        self.assertNotIn('eu5ab_rgo_start_queue', vm.vars['a'])
        self.assertNotIn('eu5ab_rgo_pending_locations', vm.lists['country'])

    def test_cancellation_clears_only_registered_location(self):
        vm = self.vm
        vm.attempt()
        vm.attempt('b')
        vm.locations['c']['queue'] = D(20)
        vm.locations['a']['queue'] = D(0)
        vm.refresh()
        self.assertEqual(self.pending(), D('1.5'))
        self.assertEqual(vm.lists['country']['eu5ab_rgo_pending_locations'], ['b'])
        self.assertEqual(vm.locations['c']['queue'], 20)

    def test_market_transfer_moves_summary_but_ownership_transfer_clears_record(self):
        vm = self.vm
        vm.attempt()
        vm.locations['a']['market'] = 'm2'
        vm.refresh()
        self.assertEqual(self.pending(), 0)
        self.assertEqual(self.pending('a'), D('1.5'))
        vm.owners['a'] = 'foreign'
        vm.refresh()
        vm.refresh('foreign')
        self.assertEqual(vm.maps['country'].get('eu5ab_rgo_pending_output_iron', {}), {})
        self.assertEqual(self.pending('a'), 0)
        self.assertEqual(vm.lists['country']['eu5ab_rgo_pending_locations'], [])
        self.assertNotIn('eu5ab_rgo_pending_owner', vm.vars['a'])
        vm.locations['d']['market'] = 'm2'
        self.assertEqual(self.pending('d'), 0)

    def test_partial_project_survives_save_restore_without_double_counting(self):
        vm = self.vm
        vm.attempt()
        vm.locations['a'].update(queue=D(0), levels=D(5), workers=D('4.6'), output=D(1))
        saved = deepcopy((vm.vars, vm.maps, vm.locations, vm.lists))
        restored = RgoDecisionVM(self.effects, self.triggers, self.values)
        restored.vars, restored.maps, restored.locations, restored.lists = saved
        restored.refresh()
        restored.refresh()
        self.assertEqual(restored.number('eu5ab_rgo_market_pending_quantity', 'b'), D('1.5'))

    def test_unknown_native_reading_retains_only_registered_group(self):
        vm = self.vm
        vm.attempt()
        vm.locations['a']['queue'] = D(-1)
        vm.locations['c']['good'] = 'silver'
        vm.refresh()
        self.assertFalse(vm.allowed('eu5ab_rgo_pending_allowed', 'b'))
        self.assertTrue(vm.allowed('eu5ab_rgo_pending_allowed', 'c'))
        self.assertEqual(vm.vars['a']['eu5ab_rgo_pending_levels'], 1)
        vm.locations['a']['queue'] = D(1)
        vm.refresh()
        self.assertEqual(self.pending(), D('1.5'))
        self.assertTrue(vm.allowed('eu5ab_rgo_pending_allowed', 'b'))

    def test_legacy_migration_requires_success_receipt_and_never_adopts_totals(self):
        for status in (1, 2, 3, 4, 5, 6, 7):
            with self.subTest(status=status):
                vm = RgoDecisionVM(self.effects, self.triggers, self.values)
                vm.vars['country'].pop('eu5ab_rgo_pending_registry_version')
                vm.locations['a'].update(queue=D(10), workers=D(3))
                vm.vars['a']['eu5ab_rgo_pending_quantity'] = D(999)
                vm.lists['country']['eu5ab_batch_rgo_records'] = [D(1)]
                for field, value in dict(status=D(status), location='a', good='goods:iron', level_before=D(4)).items():
                    vm.maps['country']['eu5ab_batch_rgo_' + field] = {D(1): value}
                vm.refresh()
                vm.refresh()
                expected = 1 if status in (4, 6) else 0
                self.assertEqual(vm.number('eu5ab_rgo_market_pending_quantity', 'b'), 0)
                self.assertEqual(vm.number('eu5ab_rgo_market_pending_unknown', 'b'), expected)
                self.assertEqual(len(vm.lists['country'].get('eu5ab_rgo_pending_locations', [])), expected)

    def test_legacy_receipt_cannot_cross_owner_or_resource_and_migrates_before_cleanup(self):
        for owner, good in (('foreign', 'iron'), ('country', 'silver')):
            vm = RgoDecisionVM(self.effects, self.triggers, self.values)
            vm.vars['country'].pop('eu5ab_rgo_pending_registry_version')
            vm.lists['country']['eu5ab_batch_rgo_records'] = [D(1)]
            for field, value in dict(status=D(6), location='a', good='goods:iron', level_before=D(4)).items():
                vm.maps['country']['eu5ab_batch_rgo_' + field] = {D(1): value}
            vm.locations['a'].update(queue=D(1), good=good)
            vm.owners['a'] = owner
            vm.refresh()
            self.assertFalse(vm.lists['country'].get('eu5ab_rgo_pending_locations'))
        # A load/month transition must recover proof before old receipts close.
        for entry, cleanup in (('eu5ab_recover_runtime_after_load', 'eu5ab_expire_old_scan_month'),
                               ('eu5ab_resume_saved_queue', 'eu5ab_batch_resume')):
            block = automation._blocks_for_token(automation.generated_fixture().effects, '\n' + entry + ' = ')[0]
            self.assertLess(block.index('eu5ab_migrate_rgo_pending_registry'), block.index(cleanup))

    def test_both_emergencies_bypass_limit_and_remain_recorded(self):
        for stock in (False, True):
            vm = RgoDecisionVM(self.effects, self.triggers, self.values)
            self.vm = vm
            vm.locations['a'].update(good='wheat', output=D(120), method='farming')
            vm.locations['b'].update(good='wheat', price=D(40), method='farming')
            vm.locations['c'].update(good='wheat', price=D(100), method='farming')
            vm.markets['m1'].update(exhaustion=not stock, stock=D('.25') if stock else D(1))
            vm.attempt('a')
            vm.refresh()
            vm.attempt('b')
            self.assertEqual(vm.calls, ['a', 'b'])
            self.assertEqual(self.pending('c'), D('31.5'))
            vm.markets['m1'].update(exhaustion=False, stock=D(1))
            vm.attempt('c')
            self.assertEqual(vm.calls, ['a', 'b'])
            self.assertEqual(vm.locations['b']['queue'], 1)

    def test_emergency_preserves_enable_staffing_forecast_and_budget_gates(self):
        vm = self.vm
        vm.locations['a'].update(good='wheat', method='farming')
        vm.markets['m1']['stock'] = D('.2')
        for setting in ('eu5ab_global_enabled', 'eu5ab_global_allow_rgo'):
            vm.vars['country'][setting] = D(0)
            self.assertFalse(vm.allowed('eu5ab_rgo_expansion_allowed'))
            vm.vars['country'][setting] = D(1)
        vm.locations['a']['paused'] = True
        self.assertFalse(vm.allowed('eu5ab_rgo_expansion_allowed'))
        vm.locations['a']['paused'] = False
        vm.locations['a']['workers'] = D(3)
        self.assertFalse(vm.allowed('eu5ab_rgo_expansion_allowed'))
        vm.locations['a'].update(workers=D(4), idle=D(0), speed=D(0))
        vm.vars['country']['eu5ab_global_rgo_workforce_mode'] = D(2)
        self.assertFalse(vm.allowed('eu5ab_rgo_expansion_allowed'))
        vm.vars['country']['eu5ab_global_rgo_workforce_mode'] = D(1)
        vm.vars['country']['eu5ab_global_budget_remaining'] = D(0)
        vm.attempt()
        self.assertEqual(vm.calls, [])

    def test_market_change_retains_builds_and_only_pauses_new_starts(self):
        vm = self.vm
        vm.markets['m1'].update(demand=D(100), supply=D(0))
        vm.locations['a']['output'] = D(120)
        vm.attempt('a')
        vm.refresh()
        self.assertTrue(vm.allowed('eu5ab_rgo_pending_allowed', 'b'))
        vm.markets['m1']['supply'] = D(200)
        vm.attempt('b')
        self.assertEqual(vm.calls, ['a'])
        self.assertEqual(vm.locations['a']['queue'], 1)
        vm.markets['m1']['demand'] = D(-1)
        self.assertFalse(vm.allowed('eu5ab_rgo_pending_allowed', 'b'))
        self.assertEqual(vm.locations['a']['queue'], 1)

    def test_current_ledger_needs_no_retired_history_or_migration(self):
        vm = self.vm
        self.assertNotIn('eu5ab_rgo_recent_', automation.generated_fixture().effects)
        self.assertNotIn('eu5ab_rgo_pending_migrated', automation.generated_fixture().effects)
        vm.attempt()
        vm.advance(4)
        self.assertEqual(vm.number('eu5ab_rgo_pending_factor', 'b'), D('.9775'))

    def test_diagnostics_distinguish_allowance_data_and_emergency(self):
        vm = self.vm
        effect = vm.definitions['eu5ab_capture_rgo_pending_diagnostics']
        vm.execute(effect, ['b'])
        self.assertEqual(vm.vars['b']['eu5ab_worker_rgo_pending_state'], 1)
        vm.locations['a']['output'] = D(120)
        vm.attempt('a')
        vm.refresh()
        vm.execute(effect, ['b'])
        self.assertEqual(vm.vars['b']['eu5ab_worker_rgo_pending_state'], 2)
        self.assertEqual(vm.vars['b']['eu5ab_worker_rgo_pending_quantity'], 30)
        vm.markets['m1']['demand'] = D(-1)
        vm.execute(effect, ['b'])
        self.assertEqual(vm.vars['b']['eu5ab_worker_rgo_pending_state'], 3)
        vm.locations['b']['good'] = 'wheat'
        vm.markets['m1']['exhaustion'] = True
        vm.execute(effect, ['b'])
        self.assertEqual(vm.vars['b']['eu5ab_worker_rgo_pending_state'], 4)


if __name__ == '__main__':
    unittest.main()
