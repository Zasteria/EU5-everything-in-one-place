"""Saved scan work and current queue phase survive rebuilding GUI continuations."""
from copy import deepcopy
import re
import unittest

from src.eu5autobuild import building_capacity, save_resume, monthly_schedule
from tests._generated import _blocks_for_token, generated_fixture
from tests._governor_script_vm import parse
from tests.test_queue_recovery_runtime import QueueVM


class SaveResumeRuntimeTests(unittest.TestCase):
    def vm(self):
        fixture = generated_fixture()
        vm = QueueVM(fixture.effects, fixture.scripted_guis)
        vm.definitions.update({k: v for k, _, v in parse(save_resume.render_effects()
                                                       + building_capacity.render_effects()
                                                       + monthly_schedule.render_effects())})
        vm.native['eu5ab_scan_month_current'] = True
        vm.stubs.update({name: lambda: None for name in (
            'eu5ab_reset_engine_candidate_watchdog_progress',
            'eu5ab_pf_rebuild_goods_index',
            'trigger_event_silently')})
        vm.stubs['eu5ab_prepare_engine_priority_phase'] = lambda: vm.calls.append(vm.vars[vm.ROOT]['eu5ab_q_phase'])
        vm.vars[vm.ROOT].update(eu5ab_scan_registry_schema_version=1, eu5ab_runtime_schema_version=2,
                                eu5ab_global_budget_mode=1, eu5ab_global_fixed_annual_budget=1000,
                                eu5ab_global_budget_limit=1000, eu5ab_global_budget_remaining=900,
                                eu5ab_q_phase=5, eu5ab_q_active=1,
                                eu5ab_q_planned_spend=100, eu5ab_q_planned_budget=100,
                                eu5ab_deep_score_attempts=240, eu5ab_scan_bucket_day=20)
        vm.run('eu5ab_ensure_annual_budget', vm.ROOT)
        return vm

    def test_completed_worker_is_retained_while_only_incomplete_worker_is_requested(self):
        vm = self.vm()
        vm.owners['pending'] = vm.ROOT
        vm.vars['pending'] = {'eu5ab_capacity_ready': 1, 'eu5ab_capacity_used': 99}
        vm.lists['pending'] = {}
        vm.vars['location']['eu5ab_worker_complete'] = 1
        vm.lists['location']['eu5ab_worker_phase_5_types'] = ['building']
        vm.lists[vm.ROOT]['eu5ab_worker_pending_locations'] = ['location', 'pending']
        completed = deepcopy((vm.vars['location'], vm.lists['location']))
        vm.run('eu5ab_recover_runtime_after_load', vm.ROOT)
        self.assertEqual((vm.vars['location'], vm.lists['location']), completed)
        self.assertTrue(vm.vars['pending']['eu5ab_capacity_requested'])
        self.assertNotIn('eu5ab_capacity_ready', vm.vars['pending'])
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_worker_pending_locations'], ['location', 'pending'])

    def test_saved_queue_revalidates_same_phase_and_settles_native_start_once(self):
        for started in (False, True):
            with self.subTest(started=started):
                vm = self.vm()
                country = vm.vars[vm.ROOT]
                vm.vars['location'].update(eu5ab_q_fire_issued=1, eu5ab_q_approved_cost=100,
                                           eu5ab_q_type_queue_before=0, eu5ab_q_type_level_before=0,
                                           eu5ab_q_material_market='market')
                vm.lists['location']['eu5ab_q_approved_types'] = ['building']
                vm.lists[vm.ROOT].update(eu5ab_q_approved_locations=['location'],
                                         eu5ab_q_phase_5_locations=['location'],
                                         eu5ab_q_phase_7_locations=['location'])
                vm.lists['location']['eu5ab_q_phase_5_types'] = ['building']
                vm.native['eu5ab_candidate_queued_levels'] = int(started)
                vm.run('eu5ab_resume_saved_queue', vm.ROOT)
                self.assertEqual(country['eu5ab_global_budget_remaining'], 800 if started else 900)
                self.assertEqual(country['eu5ab_global_budget_spent'], 200 if started else 100)
                self.assertEqual(country['eu5ab_q_planned_spend'], 0)
                self.assertEqual(country['eu5ab_deep_score_attempts'], 240)
                self.assertEqual(country['eu5ab_scan_bucket_day'], 20)
                self.assertEqual(vm.calls, [5])
                self.assertEqual(vm.lists[vm.ROOT]['eu5ab_q_phase_7_locations'], ['location'])
                self.assertEqual(vm.lists['location']['eu5ab_q_phase_5_types'], ['building'])
                vm.run('eu5ab_resume_saved_queue', vm.ROOT)
                self.assertEqual(country['eu5ab_global_budget_remaining'], 800 if started else 900)

    def test_late_gui_callbacks_cannot_advance_or_charge_during_load_recovery(self):
        vm = self.vm()
        vm.vars[vm.ROOT].update(eu5ab_scan_resume_after_load=1, eu5ab_q_fire=1,
                                eu5ab_q_expected=0, eu5ab_monthly_build_quota=10)
        vm.lists['location']['eu5ab_q_approved_types'] = ['building']
        vm.vars['location'].update(eu5ab_q_fire_issued=1, eu5ab_q_approved_cost=100)
        vm.native['eu5ab_candidate_queued_levels'] = 1
        before = deepcopy((vm.vars, vm.lists))
        for name, root in (('eu5ab_gui_queue_sync_check', vm.ROOT),
                           ('eu5ab_gui_queue_confirm_sync', vm.ROOT),
                           ('eu5ab_gui_queue_confirm_candidate', 'location')):
            script = _blocks_for_token(generated_fixture().scripted_guis, '\n' + name + ' = ')[0]
            vm.definitions[name] = parse(re.sub(r'saved_scopes = \{[^}]*\}', '', script))[0][2]
            vm.run(name, root)
            self.assertEqual((vm.vars, vm.lists), before)


if __name__ == '__main__':
    unittest.main()
