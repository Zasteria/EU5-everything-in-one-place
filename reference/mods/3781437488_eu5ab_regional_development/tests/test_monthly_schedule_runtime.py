"""Execute calendar boundaries and saved approval settlement from generated code."""
from copy import deepcopy
import re
import unittest

from src.eu5autobuild import monthly_schedule
from tests._generated import generated_fixture, _blocks_for_token
from tests._governor_script_vm import parse
from tests import test_save_resume_runtime as resume_runtime


class MonthlyScheduleRuntimeTests(unittest.TestCase):
    def vm(self):
        vm = resume_runtime.SaveResumeRuntimeTests().vm()
        vm.native.pop('eu5ab_scan_month_current')
        vm.capacity_triggers.update({k: v for k, _, v in parse(monthly_schedule.render_triggers())})
        vm.day, vm.month_number, vm.year = 23, 5, 1410
        vm.vars[vm.ROOT].update(eu5ab_scan_year=1410, eu5ab_scan_month=5,
                                eu5ab_scan_round_active=1, eu5ab_global_enabled=1)
        fixture = generated_fixture()
        for name in ('eu5ab_clear_engine_candidate_queue', 'eu5ab_clear_location_candidate_state',
                     'eu5ab_clear_location_worker_state', 'eu5ab_clear_backfill_worker_state',
                     'eu5ab_clear_backfill_scratch',
                     'eu5ab_clear_worker_screening', 'eu5ab_clear_rgo_screening',
                     'eu5ab_clear_scan_continuation', 'eu5ab_reset_committed_construction_demand'):
            vm.definitions[name] = parse(_blocks_for_token(fixture.effects, '\n' + name + ' = ')[0])[0][2]
        for name, _, body in parse(fixture.events):
            if name in ('eu5ab_monthly.1', 'eu5ab_monthly.2', 'eu5ab_monthly.3', 'eu5ab_monthly.4'):
                vm.definitions[name] = dict((k, v) for k, _, v in body)['immediate']
        pulse = parse(_blocks_for_token(fixture.on_actions, '\neu5ab_monthly_country_policy_pulse = ')[0])[0][2]
        vm.definitions['monthly_pulse'] = dict((k, v) for k, _, v in pulse)['effect']
        vm.native['is_human'] = True
        vm.scheduled = []
        # This boundary observes dispatches; date gates, cleanup and economic
        # settlement execute unchanged from the generated script.
        original = vm.execute
        def execute(entries, stack):
            if len(entries) == 1 and entries[0][0] == 'trigger_event_silently':
                vm.scheduled.append(dict((k, v) for k, _, v in entries[0][2]))
            else:
                original(entries, stack)
        vm.execute = execute
        return vm

    def test_late_gui_and_rgo_fire_are_blocked_before_23_or_for_an_old_month(self):
        vm = self.vm()
        fixture = generated_fixture()
        from src.eu5autobuild import building_capacity
        fire_guis = {k: v for k, _, v in parse(re.sub(
            r'saved_scopes = \{[^}]*\}', '', building_capacity.render_guis()))}
        vm.definitions['eu5ab_gui_queue_request_fire'] = fire_guis['eu5ab_gui_queue_request_fire']
        vm.definitions['eu5ab_try_construct_rgo_need'] = parse(_blocks_for_token(
            fixture.effects, '\neu5ab_try_construct_rgo_need = ')[0])[0][2]
        vm.vars[vm.ROOT]['eu5ab_q_fire'] = 1
        vm.vars['location']['eu5ab_q_location_approved'] = 1
        vm.lists['location']['eu5ab_q_approved_types'] = ['building']
        shown = dict((k, v) for k, _, v in fire_guis['eu5ab_gui_queue_fire_permitted'])['is_shown']
        for day, month in ((8, 5), (9, 5), (21, 5), (22, 5), (23, 6)):
            vm.day, vm.month_number = day, month
            before = deepcopy((vm.vars, vm.lists, vm.variable_maps))
            self.assertFalse(vm.condition(shown, ['location']))
            vm.run('eu5ab_gui_queue_request_fire', 'location')
            vm.run('eu5ab_gui_queue_try_candidate', 'location')
            vm.run('eu5ab_try_construct_rgo_need', 'location')
            self.assertEqual((vm.vars, vm.lists, vm.variable_maps), before)

    def test_calendar_days_and_year_month_identity(self):
        vm = self.vm()
        for day, scan, queue in ((1, False, False), (2, True, False), (21, True, False),
                                  (22, True, False), (23, False, True), (28, False, True), (31, False, True)):
            vm.day = day
            self.assertEqual(vm.test('eu5ab_scan_calendar_open', '=', 'yes', [vm.ROOT]), scan)
            self.assertEqual(vm.test('eu5ab_queue_calendar_open', '=', 'yes', [vm.ROOT]), queue)
        for year, month in ((1410, 6), (1411, 5)):
            vm.year, vm.month_number = year, month
            self.assertFalse(vm.test('eu5ab_scan_month_current', '=', 'yes', [vm.ROOT]))
            self.assertFalse(vm.test('eu5ab_queue_calendar_open', '=', 'yes', [vm.ROOT]))
        # February and December use the same month identity contract.
        for year, month, day in ((1410, 2, 28), (1410, 12, 31), (1411, 1, 23)):
            vm.year, vm.month_number, vm.day = year, month, day
            vm.run('eu5ab_stamp_scan_month', vm.ROOT)
            self.assertTrue(vm.test('eu5ab_queue_calendar_open', '=', 'yes', [vm.ROOT]))

    def test_month_expiry_settles_physical_start_once_and_discards_unexecuted_work(self):
        for started in (False, True):
            with self.subTest(started=started):
                vm = self.vm()
                country = vm.vars[vm.ROOT]
                vm.vars['location'].update(eu5ab_q_fire_issued=1, eu5ab_q_approved_cost=100,
                                           eu5ab_q_type_queue_before=0, eu5ab_q_type_level_before=0,
                                           eu5ab_q_material_market='market', eu5ab_worker_complete=1,
                                           eu5ab_pl_output_floor=7)
                vm.lists['location'].update(eu5ab_q_approved_types=['building'],
                                             eu5ab_worker_phase_5_types=['building'])
                vm.lists[vm.ROOT].update(eu5ab_q_approved_locations=['location'],
                                         eu5ab_q_phase_5_locations=['location'],
                                         eu5ab_worker_pending_locations=['location'],
                                         eu5ab_scan_unscanned_locations=['location'])
                vm.native['eu5ab_candidate_queued_levels'] = int(started)
                vm.month_number, vm.day = 6, 1
                vm.run('eu5ab_expire_old_scan_month', vm.ROOT)
                self.assertEqual(country['eu5ab_global_budget_remaining'], 800 if started else 900)
                self.assertEqual(country['eu5ab_global_budget_spent'], 200 if started else 100)
                self.assertEqual(country['eu5ab_q_planned_spend'], 0)
                self.assertEqual(country['eu5ab_deep_score_attempts'], 240)
                self.assertNotIn('eu5ab_scan_round_active', country)
                self.assertNotIn('eu5ab_q_active', country)
                self.assertFalse(vm.lists[vm.ROOT]['eu5ab_scan_unscanned_locations'])
                self.assertFalse(vm.lists['location']['eu5ab_q_approved_types'])
                self.assertEqual(vm.vars['location']['eu5ab_pl_output_floor'], 7)
                self.assertEqual(vm.native['eu5ab_candidate_queued_levels'], int(started))
                after = deepcopy((vm.vars, vm.lists, vm.variable_maps))
                vm.run('eu5ab_expire_old_scan_month', vm.ROOT)
                self.assertEqual((vm.vars, vm.lists, vm.variable_maps), after)

    def test_stale_refill_and_finalize_cannot_delay_new_month_pulse(self):
        vm = self.vm()
        vm.vars[vm.ROOT].update(eu5ab_scan_refill_active=1, eu5ab_scan_finalizing=1)
        vm.lists[vm.ROOT]['eu5ab_scan_unscanned_locations'] = ['location']
        vm.month_number, vm.day = 6, 1
        for name in ('eu5ab_monthly.2', 'eu5ab_monthly.3'):
            vm.run(name, vm.ROOT)
        self.assertEqual(vm.scheduled, [])
        vm.vars['location']['eu5ab_policy_id'] = 1
        vm.run('monthly_pulse', vm.ROOT)
        self.assertEqual(vm.scheduled, [{'id': 'eu5ab_monthly.1', 'days': '1'}])
        self.assertNotIn('eu5ab_scan_next_month_pending', vm.vars[vm.ROOT])

    def test_expiry_does_not_clear_transferred_location_new_owner_work(self):
        vm = self.vm()
        vm.owners['location'] = 'foreign'
        vm.vars['location'].update(eu5ab_capacity_worker_country='foreign', eu5ab_worker_complete=1,
                                   eu5ab_pending_approval_country='foreign', eu5ab_q_fire_issued=1)
        vm.lists['location']['eu5ab_q_approved_types'] = ['building']
        vm.lists[vm.ROOT].update(eu5ab_q_phase_5_locations=['location'],
                                 eu5ab_q_approved_locations=['location'],
                                 eu5ab_worker_pending_locations=['location'])
        before = deepcopy((vm.vars['location'], vm.lists['location']))
        vm.month_number, vm.day = 6, 1
        vm.run('eu5ab_expire_old_scan_month', vm.ROOT)
        self.assertEqual((vm.vars['location'], vm.lists['location']), before)
        self.assertFalse(vm.lists[vm.ROOT]['eu5ab_q_approved_locations'])

    def test_legacy_queue_without_month_stamp_is_closed_on_load(self):
        vm = self.vm()
        vm.vars[vm.ROOT].pop('eu5ab_scan_month')
        vm.run('eu5ab_recover_runtime_after_load', vm.ROOT)
        self.assertNotIn('eu5ab_q_active', vm.vars[vm.ROOT])
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_global_budget_remaining'], 900)


if __name__ == '__main__':
    unittest.main()
