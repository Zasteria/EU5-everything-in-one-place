"""Daily registered-record maintenance independent of construction activity."""
from copy import deepcopy
import unittest

from tests._generated import generated_fixture
from tests._governor_script_vm import parse
from tests.test_production_cohorts_runtime import CohortVM


class MaintenanceVM(CohortVM):
    def __init__(self):
        super().__init__()
        self.scheduled = []
        self.stubs.pop('trigger_event_silently')
        event = next(v for k, _, v in parse(generated_fixture().events)
                     if k == 'eu5ab_pf_maintenance.1')
        self.definitions['maintenance_event'] = next(v for k, _, v in event if k == 'immediate')

    def execute(self, entries, stack):
        if len(entries) == 1 and entries[0][0] == 'trigger_event_silently':
            fields = dict((k, v) for k, _, v in entries[0][2])
            self.scheduled.append((stack[-1], fields['id'], self.value(fields['days'], stack)))
            return
        if any(k == 'trigger_event_silently' for k, _, _ in entries):
            batch = []
            for entry in entries:
                if entry[0] == 'trigger_event_silently':
                    super().execute(batch, stack)
                    self.execute([entry], stack)
                    batch = []
                else:
                    batch.append(entry)
            return super().execute(batch, stack)
        return super().execute(entries, stack)

    def tick(self):
        self.run('maintenance_event', self.ROOT)


class ProductionMaintenanceRuntimeTests(unittest.TestCase):
    def test_no_registered_projects_schedule_no_background_work(self):
        vm = MaintenanceVM()
        vm.run('eu5ab_pf_resume_maintenance', vm.ROOT)
        vm.tick()
        self.assertEqual(vm.scheduled, [])

    def test_completion_is_observed_after_monthly_scan_and_queue_have_stopped(self):
        vm = MaintenanceVM()
        vm.day = 25
        ident = vm.start()
        self.assertEqual(vm.scheduled, [(vm.ROOT, 'eu5ab_pf_maintenance.1', 1)])
        vm.day = 26
        vm.facts['foundry'].update(building_level=1, building_levels_under_construction=0,
                                    building_employment_size_amount=1000,
                                    building_employed_amount=250)
        vm.tick()
        self.assertEqual(vm.record(ident, 'state'), 1)
        self.assertEqual(vm.pending(), 7.5)
        self.assertEqual(vm.deadline(ident), vm.value('eu5ab_pl_today', [vm.ROOT]) + 12 * 31)
        self.assertNotIn('eu5ab_scan_active', vm.vars[vm.ROOT])
        self.assertNotIn('eu5ab_q_active', vm.vars[vm.ROOT])
        self.assertEqual(len(vm.scheduled), 2)

    def test_multiple_starts_and_duplicate_events_coalesce(self):
        vm = MaintenanceVM()
        vm.start()
        vm.start(queue_before=1)
        self.assertEqual(len(vm.scheduled), 1)
        vm.tick()  # Before the scheduled next day: no action or new event.
        self.assertEqual(len(vm.scheduled), 1)
        vm.day += 1
        vm.tick()
        vm.tick()
        self.assertEqual(len(vm.scheduled), 2)
        vm.day += 1
        vm.tick()
        self.assertEqual(len(vm.scheduled), 3)

    def test_load_rearms_once_without_extending_existing_completion_deadline(self):
        vm = MaintenanceVM()
        ident = vm.start(immediate=True)
        vm.observe(1, 0, 200)
        deadline = vm.deadline(ident)
        restored = deepcopy(vm)
        restored.run('eu5ab_pf_resume_maintenance', restored.ROOT)
        self.assertEqual(len(restored.scheduled), 2)
        restored.day += 1
        restored.tick()  # Either the saved event or the new one arrives first.
        restored.tick()
        self.assertEqual(len(restored.scheduled), 3)
        self.assertEqual(restored.deadline(ident), deadline)

    def test_expiry_and_cancellation_stop_rescheduling(self):
        for completed in (False, True):
            with self.subTest(completed=completed):
                vm = MaintenanceVM()
                ident = vm.start(immediate=completed)
                if completed:
                    vm.year += 1
                else:
                    vm.day += 1
                    vm.facts['foundry']['building_levels_under_construction'] = 0
                vm.tick()
                self.assertIsNone(vm.record(ident, 'state'))
                self.assertEqual(len(vm.scheduled), 1)
                self.assertNotIn('eu5ab_pf_maintenance_after', vm.vars[vm.ROOT])
                vm.tick()
                self.assertEqual(len(vm.scheduled), 1)

    def test_staffing_release_continues_while_building_is_closed_and_automation_disabled(self):
        vm = MaintenanceVM()
        ident = vm.start(immediate=True)
        vm.observe(1, 0, 250)
        deadline = vm.deadline(ident)
        vm.vars[vm.ROOT]['eu5ab_global_enabled'] = 0
        vm.facts['foundry'].update(building_employed_amount=1000, is_opened=False)
        vm.day += 1
        vm.tick()
        self.assertEqual(vm.pending(), 0)
        self.assertEqual(vm.deadline(ident), deadline)
        self.assertEqual(len(vm.scheduled), 2)

    def test_unchanged_refreshes_coalesce_and_native_mutation_can_force_refresh(self):
        vm = MaintenanceVM()
        vm.start()
        vm.day += 1
        refresh = vm.definitions['eu5ab_refresh_build_pending']
        rebuilds = []
        vm.stubs['eu5ab_refresh_build_pending'] = lambda: (
            rebuilds.append(1), vm.execute(refresh, [vm.ROOT]))
        for _ in range(10):
            vm.run('eu5ab_ensure_build_pending', vm.ROOT)
        self.assertEqual(len(rebuilds), 1)
        vm.tick()
        self.assertEqual(len(rebuilds), 1)
        vm.vars[vm.ROOT]['eu5ab_build_pending_dirty'] = True
        vm.run('eu5ab_ensure_build_pending', vm.ROOT)
        self.assertEqual(len(rebuilds), 2)
        vm.day += 1
        vm.run('eu5ab_ensure_build_pending', vm.ROOT)
        self.assertEqual(len(rebuilds), 3)

    def test_daily_maintenance_crosses_a_short_month_without_waiting_for_a_scan(self):
        vm = MaintenanceVM()
        vm.month_number, vm.day = 2, 28
        ident = vm.start()
        vm.month_number, vm.day = 3, 1
        vm.tick()
        self.assertEqual(vm.record(ident, 'state'), 0)
        self.assertEqual(vm.pending(), 10)
        self.assertEqual(len(vm.scheduled), 2)


if __name__ == '__main__':
    unittest.main()
