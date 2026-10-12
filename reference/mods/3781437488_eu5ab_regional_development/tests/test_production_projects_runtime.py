"""Registration chooses only the exact instance changed by its command."""
import unittest
from tests.test_production_cohorts_runtime import CohortVM


class ProductionProjectsRuntimeTests(unittest.TestCase):
    def test_legacy_confirmation_without_a_new_exact_snapshot_cannot_enroll(self):
        vm = CohortVM()
        vm.facts['foundry'].update(building_level=20, building_levels_under_construction=4)
        vm.vars['location'].update(eu5ab_q_fire_issued=1, eu5ab_q_type_level_before=19,
                                    eu5ab_q_type_queue_before=3)
        vm.run('eu5ab_pf_register_start')
        self.assertFalse(vm.lists[vm.ROOT].get('eu5ab_pf_cohorts'))

    def test_snapshot_must_match_type_and_owner(self):
        for field, wrong in (('eu5ab_pf_start_type', 'building_type:iron_mill'),
                             ('eu5ab_pf_start_owner', 'foreign')):
            with self.subTest(field=field):
                vm = CohortVM()
                vm.run('eu5ab_pf_capture_start_geometry')
                vm.vars['location'][field] = wrong
                vm.facts['foundry']['building_levels_under_construction'] = 1
                vm.run('eu5ab_pf_register_start')
                self.assertFalse(vm.lists[vm.ROOT].get('eu5ab_pf_cohorts'))

    def test_confirmation_of_a_preexisting_unchanged_queue_enrolls_nothing(self):
        vm = CohortVM()
        vm.facts['foundry'].update(building_level=2, building_levels_under_construction=4)
        vm.run('eu5ab_pf_capture_start_geometry')
        vm.run('eu5ab_pf_register_start')
        self.assertFalse(vm.lists[vm.ROOT].get('eu5ab_pf_cohorts'))

    def test_one_confirmation_enrolls_once_even_if_native_delta_is_larger(self):
        vm = CohortVM()
        vm.run('eu5ab_pf_capture_start_geometry')
        vm.facts['foundry']['building_levels_under_construction'] = 4
        vm.run('eu5ab_pf_register_start')
        vm.run('eu5ab_pf_register_start')
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_pf_cohorts'], [1])
        self.assertEqual(vm.value('eu5ab_pf_queued_value', ['foundry']), 1)

    def test_immediate_completion_is_idempotent(self):
        vm = CohortVM()
        ident = vm.start(immediate=True)
        self.assertEqual(vm.record(ident, 'state'), 1)
        deadline = vm.deadline(ident)
        for _ in range(3):
            vm.observe(1, 0, 200)
            self.assertEqual(vm.deadline(ident), deadline)
        self.assertEqual(vm.pending(), 8)

    def test_exact_snapshot_ignores_unchanged_same_type_sibling(self):
        vm = CohortVM()
        vm.building_locations['sibling'] = 'location'
        vm.building_types['sibling'] = vm.building_types['foundry']
        vm.vars['sibling'], vm.lists['sibling'] = {}, {}
        vm.facts['sibling'] = dict(building_level=20, building_levels_under_construction=8)
        vm.buildings['location'].insert(0, 'sibling')
        ident = vm.start(before=2, queue_before=4)
        self.assertEqual(vm.record(ident, 'building'), 'foundry')
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_pf_cohorts'], [1])

    def test_transferred_geometry_is_not_reused_by_new_owner(self):
        vm = CohortVM()
        vm.start()
        vm.owners['location'] = 'new_country'
        vm.vars['new_country'] = dict(eu5ab_global_job_fill_deadline_months=12)
        vm.lists['new_country'] = {}
        vm.run('eu5ab_pf_capture_start_geometry')
        vm.facts['foundry']['building_levels_under_construction'] = 4
        vm.run('eu5ab_pf_register_start')
        self.assertEqual(vm.variable_maps['new_country']['eu5ab_pf_c_building'], {1: 'foundry'})
        self.assertEqual(vm.value('eu5ab_pf_queued_value', ['foundry']), 1)


if __name__ == '__main__':
    unittest.main()
