"""A frozen plan and save/load must not resurrect a synchronous dispatch guard."""
from copy import deepcopy
import unittest

from src.eu5autobuild.queue_bridge import _block
from tests._generated import generated_fixture
from tests._governor_script_vm import parse
from tests.test_manual_decisions_runtime import ManualVM


class BatchLockRuntimeTests(unittest.TestCase):
    def test_planning_dispatch_clears_guard_and_next_month_builds_with_reentry_protected(self):
        vm = ManualVM()
        vm.manual()
        c = vm.vars[vm.ROOT]
        c.update(eu5ab_monthly_build_quota=1, eu5ab_batch_phase=5,
                 eu5ab_q_phase=5, eu5ab_constructions_started_this_tick=0)
        # Exercise the real finish -> snapshot -> batch/queue cleanup chain.
        for name in ('eu5ab_finish_engine_candidate_queue',
                     'eu5ab_finish_engine_candidate_queue_live',
                     'eu5ab_clear_engine_candidate_queue',
                     'eu5ab_clear_worker_screening', 'eu5ab_settle_scan_candidate_batch',
                     'eu5ab_complete_scan_round', 'eu5ab_clear_scan_continuation'):
            vm.definitions.update({k: v for k, _, v in parse(_block(generated_fixture().effects, name))})
            vm.stubs.pop(name, None)
        # This native global-demand cleanup does not touch the dispatch guard.
        vm.stubs['eu5ab_reset_committed_construction_demand'] = lambda: None
        nested_calls = []

        def reenter():
            if c.get('eu5ab_batch_running'):
                before = deepcopy((vm.vars, vm.lists, vm.variable_maps, vm.commands))
                vm.run('eu5ab_dispatch_construction_batch', vm.ROOT)
                self.assertEqual((vm.vars, vm.lists, vm.variable_maps, vm.commands), before)
                nested_calls.append(True)

        vm.stubs['eu5ab_batch_update_market_scores'] = reenter
        vm.add('building_type:planned', 20, '100')
        vm.lists[vm.ROOT]['eu5ab_manual_locations'] = ['location']
        vm.run('eu5ab_dispatch_construction_batch', vm.ROOT)
        self.assertTrue(c['eu5ab_manual_ready'])
        self.assertTrue(nested_calls)
        self.assertEqual(vm.commands, [])
        for scope in (vm.ROOT, 'location'):
            self.assertNotIn('eu5ab_batch_running', vm.vars[scope])

        vm.day = 23
        vm.run('eu5ab_manual_execute', vm.ROOT)
        vm.run('eu5ab_manual_execute', vm.ROOT)
        self.assertEqual([row[2] for row in vm.commands], ['building_type:planned'])
        self.assertNotIn('eu5ab_batch_running', c)
        vm.month_number = 6
        vm.stubs['eu5ab_sync_cmm_settings'] = lambda: None
        vm.run('eu5ab_manual_expire', vm.ROOT)
        c.update(eu5ab_scan_month=6, eu5ab_q_active=1, eu5ab_q_phase=5,
                 eu5ab_batch_phase=5, eu5ab_constructions_started_this_tick=0)
        vm.add('building_type:next_month', 20, '100')
        vm.run('eu5ab_dispatch_construction_batch', vm.ROOT)
        self.assertEqual([row[2] for row in vm.commands],
                         ['building_type:planned', 'building_type:next_month'])
        self.assertNotIn('eu5ab_batch_running', c)

    def test_plan_snapshot_restore_and_discard_preserve_a_live_guard(self):
        for operation in ('eu5ab_manual_finish', 'eu5ab_manual_restore_scope', 'eu5ab_manual_discard'):
            with self.subTest(operation=operation):
                vm = ManualVM()
                vm.manual()
                vm.lists[vm.ROOT]['eu5ab_manual_locations'] = ['location']
                for scope in (vm.ROOT, 'location'):
                    vm.vars[scope]['eu5ab_batch_running'] = 1
                vm.run(operation, vm.ROOT)
                if operation == 'eu5ab_manual_restore_scope':
                    vm.run(operation, 'location')
                for scope in (vm.ROOT, 'location'):
                    self.assertEqual(vm.vars[scope]['eu5ab_batch_running'], 1)

    def test_load_unlocks_ordinary_queue_and_ready_plan_before_recovery(self):
        action = parse(_block(generated_fixture().on_actions, 'eu5ab_on_cmf_after_load'))[0][2]
        effect = next(v for k, _, v in action if k == 'effect')
        for planned in (False, True):
            with self.subTest(planned=planned):
                vm = ManualVM()
                c = vm.vars[vm.ROOT]
                c.update(eu5ab_monthly_build_quota=1, eu5ab_batch_phase=5,
                         eu5ab_constructions_started_this_tick=0)
                if planned:
                    vm.manual()
                project = vm.add('building_type:after_load', 20, '100')
                if planned:
                    vm.run('eu5ab_batch_approve', vm.ROOT)
                    vm.run('eu5ab_batch_issue', vm.ROOT)
                    vm.lists[vm.ROOT]['eu5ab_manual_locations'] = ['location']
                    vm.run('eu5ab_manual_finish', vm.ROOT)
                c['eu5ab_batch_running'] = 1
                budget_before = c['eu5ab_global_budget_spent']
                recovered = []

                def recover():
                    self.assertNotIn('eu5ab_batch_running', c)
                    recovered.append(True)

                # Native scheduling/maintenance are separate from the load hook;
                # verify the guard is gone before ordinary recovery is entered.
                for name in ('eu5ab_mark_interrupted_scan_on_load', 'eu5ab_sync_cmm_settings',
                             'eu5ab_schedule_scan_resume_after_load', 'eu5ab_ensure_annual_budget'):
                    vm.stubs[name] = lambda: None
                vm.stubs['eu5ab_recover_runtime_after_load'] = recover
                vm.execute(effect, [vm.ROOT])
                self.assertNotIn('eu5ab_batch_running', c)
                self.assertEqual(c['eu5ab_global_budget_spent'], budget_before)
                self.assertEqual(vm.commands, [])
                self.assertEqual(bool(recovered), not planned)
                vm.day = 23
                if planned:
                    vm.run('eu5ab_manual_execute', vm.ROOT)
                else:
                    vm.run('eu5ab_dispatch_construction_batch', vm.ROOT)
                self.assertEqual([row[0] for row in vm.commands], [project])
                self.assertNotIn('eu5ab_batch_running', c)


if __name__ == '__main__':
    unittest.main()
