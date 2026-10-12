"""Native readings drive the emitted queue guards and per-project ledger."""
import math
import unittest

from src.eu5autobuild.construction_slots import remaining
from tests._generated import generated_fixture
from tests.test_queue_recovery_runtime import QueueVM


class ParallelConstructionRuntimeTests(unittest.TestCase):
    def test_supplemental_phases_recheck_food_emergency_priority(self):
        from tests._governor_script_vm import parse
        from tests._generated import _blocks_for_token
        vm = self.vm()
        name = 'eu5ab_engine_candidate_in_current_priority_phase'
        vm.capacity_triggers.update({k: v for k, _, v in parse(_blocks_for_token(generated_fixture().triggers, name + ' = ')[0])})
        for rank in range(1, 5):
            vm.native[f'eu5ab_engine_candidate_feature_rank_{rank}'] = rank == 1
        for phase in (9, 13):
            vm.vars[vm.ROOT]['eu5ab_q_phase'] = phase
            for emergency in (False, True):
                vm.native['eu5ab_engine_candidate_is_food_emergency'] = emergency
                self.assertEqual(vm.test(name, '=', 'yes', ['location']), emergency == (phase == 9))

    def vm(self):
        fixture = generated_fixture()
        return QueueVM(fixture.effects, fixture.scripted_guis)

    def test_dynamic_capacity_includes_any_modifier_source_and_existing_work(self):
        self.assertEqual(remaining(4, 2, 1), 1)
        self.assertEqual(remaining(2, 1), 1)
        self.assertEqual(remaining(1.9, 1), 0)
        for limit in (None, math.nan, math.inf, 0):
            self.assertEqual(remaining(limit, 0), 0)
        vm = self.vm()
        vm.native.update({'modifier:max_constructions_at_same_time': 3,
                          'num_civil_constructions': 1})
        vm.scopes.update(eu5ab_engine_parallel_modifier=3,
                         eu5ab_engine_queue_has_room=True, eu5ab_engine_queue_count=2)
        self.assertFalse(vm.test('eu5ab_engine_has_parallel_room', '=', 'yes', ['location']))
        vm.run('eu5ab_capture_parallel_queue')
        self.assertFalse(vm.test('eu5ab_engine_has_parallel_room', '=', 'yes', ['location']))
        vm.scopes['eu5ab_engine_queue_count'] = 1
        vm.run('eu5ab_capture_parallel_queue')
        self.assertTrue(vm.test('eu5ab_engine_has_parallel_room', '=', 'yes', ['location']))
        self.assertEqual(vm.vars['location']['eu5ab_parallel_limit'], 2)
        # Another manual project invalidates the old reading, even if room remains.
        vm.native['num_civil_constructions'] = 2
        self.assertFalse(vm.test('eu5ab_engine_has_parallel_room', '=', 'yes', ['location']))
        vm.scopes['eu5ab_engine_queue_count'] = 2
        vm.run('eu5ab_capture_parallel_queue')
        self.assertTrue(vm.test('eu5ab_engine_has_parallel_room', '=', 'yes', ['location']))
        self.assertEqual(vm.vars['location']['eu5ab_parallel_limit'], 3)
        vm.scopes['eu5ab_engine_queue_has_room'] = False
        vm.run('eu5ab_capture_parallel_queue')
        self.assertFalse(vm.test('eu5ab_engine_has_parallel_room', '=', 'yes', ['location']))
        vm.scopes['eu5ab_engine_queue_has_room'] = True
        vm.run('eu5ab_capture_parallel_queue')
        self.assertTrue(vm.test('eu5ab_engine_has_parallel_room', '=', 'yes', ['location']))
        vm.native['modifier:max_constructions_at_same_time'] = 2
        self.assertFalse(vm.test('eu5ab_engine_has_parallel_room', '=', 'yes', ['location']))

    def test_unrelated_civil_queue_growth_is_not_a_building_confirmation(self):
        vm = self.vm()
        vm.vars['location']['eu5ab_q_fire_issued'] = True
        vm.native['num_civil_constructions'] = 2
        self.assertFalse(vm.test('eu5ab_approved_building_started', '=', 'yes', ['location']))
        vm.native['eu5ab_candidate_queued_levels'] = 1
        self.assertTrue(vm.test('eu5ab_approved_building_started', '=', 'yes', ['location']))

    def test_repeated_type_completions_cancellations_and_legacy_count(self):
        vm = self.vm()
        for _ in range(2):
            vm.run('eu5ab_record_confirmed_building')
        maps = vm.variable_maps['location']
        self.assertEqual(maps['eu5ab_active_building_counts']['building'], 2)
        self.assertEqual(vm.lists['location']['eu5ab_active_building_types'], ['building'])
        vm.native.update({'location_building_level(scope:eu5ab_candidate_building)': 1,
                          'eu5ab_candidate_queued_levels': 1})
        vm.vars[vm.ROOT]['eu5ab_diag_active_mod_projects'] = 0
        vm.run('eu5ab_refresh_active_building_type')
        self.assertEqual(maps['eu5ab_active_building_counts']['building'], 1)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_diag_active_mod_projects'], 1)
        vm.native['eu5ab_candidate_queued_levels'] = 0
        vm.run('eu5ab_refresh_active_building_type')
        self.assertEqual(vm.lists['location']['eu5ab_active_building_types'], [])
        vm.lists['location']['eu5ab_active_building_types'] = ['building']
        maps['eu5ab_active_building_baselines']['building'] = 1
        vm.native['eu5ab_candidate_queued_levels'] = 1
        vm.run('eu5ab_refresh_active_building_type')
        self.assertEqual(maps['eu5ab_active_building_counts']['building'], 1)

    def test_cooldown_is_applied_once_after_dispatch_batch(self):
        vm = self.vm()
        vm.run('eu5ab_record_queue_start_location')
        vm.run('eu5ab_record_queue_start_location')
        self.assertNotIn('eu5ab_build_cooldown', vm.vars['location'])
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_q_started_locations'], ['location'])
        vm.run('eu5ab_apply_queue_cooldowns', vm.ROOT)
        self.assertGreater(vm.vars['location']['eu5ab_build_cooldown'], 0)
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_q_started_locations'], [])

    def test_manual_completion_does_not_erase_mod_projects_of_the_same_type(self):
        vm = self.vm()
        vm.run('eu5ab_record_confirmed_building')
        vm.run('eu5ab_record_confirmed_building')
        # A manual level completed, while both Mod levels are still queued.
        vm.native.update({'location_building_level(scope:eu5ab_candidate_building)': 1,
                          'eu5ab_candidate_queued_levels': 2})
        vm.run('eu5ab_refresh_active_building_type')
        self.assertEqual(vm.variable_maps['location']['eu5ab_active_building_counts']['building'], 2)

    def test_profit_final_order_applies_price_once_and_retains_true_profit(self):
        vm = self.vm()
        vm.run('eu5ab_capture_building_capacity')
        vm.native['scope:eu5ab_candidate_building.eu5ab_current_candidate_configured_priority'] = 0
        vm.native['scope:eu5ab_candidate_building.eu5ab_output_price_factor'] = .5
        for profit, rank in ((10, 5), (-10, -20)):
            vm.lists['location']['eu5ab_q_profit_best_types'] = []
            vm.scopes['eu5ab_engine_profit'] = profit
            vm.run('eu5ab_record_actual_profit_candidate')
            self.assertEqual(vm.vars['location']['eu5ab_q_profit_best_rank'], rank)
            self.assertEqual(vm.vars['location']['eu5ab_q_profit_best_actual'], profit)


if __name__ == '__main__':
    unittest.main()
