"""Execute generated Mod records, deadlines and native staffing arithmetic.

Native PM identities, type efficiencies and employment are explicit test
inputs. This verifies script state, not the meaning/timing of game APIs.
"""
from copy import deepcopy
import re
import unittest

from tests.test_market_supply_runtime import SupplyVM


class CohortVM(SupplyVM):
    def __init__(self):
        super().__init__()
        self.stubs.pop('eu5ab_pf_refresh_projects')
        self.stubs.pop('eu5ab_pf_confirm_start')
        self.year, self.month_number, self.day = 1436, 5, 2
        self.facts['foundry'].update(building_level=0, building_levels_under_construction=0,
                                      building_employed_amount=0, building_employment_size_amount=0)
        self.building_locations['donor'] = 'second'
        self.building_types['donor'] = self.building_types['foundry']
        self.active_methods['donor'] = list(self.active_methods['foundry'])
        self.facts['donor'] = dict(building_level=1, building_employed_amount=1000,
                                  building_employment_size_amount=1000, is_opened=True)
        self.vars['donor'], self.lists['donor'] = {}, {}
        self.buildings['second'] = ['donor']
        self.vars['location']['eu5ab_pf_reference_building'] = 'donor'
        self.efficiencies = {'location': 5, 'second': 5}

    def start(self, before=0, queue_before=0, *, known=True, immediate=False):
        self.facts['foundry'].update(building_level=before,
                                    building_levels_under_construction=queue_before,
                                    building_employment_size_amount=before * 1000)
        if known:
            self.vars['location']['eu5ab_pf_reference_building'] = 'foundry' if before else 'donor'
        else:
            self.vars['location'].pop('eu5ab_pf_reference_building', None)
        self.vars['location'].update(eu5ab_q_type_level_before=before,
                                      eu5ab_q_type_queue_before=queue_before)
        self.run('eu5ab_reserve_candidate_output')
        self.run('eu5ab_pf_capture_start_geometry')
        self.facts['foundry'].update(building_level=before + int(immediate),
                                    building_levels_under_construction=queue_before + int(not immediate),
                                    building_employment_size_amount=(before + int(immediate)) * 1000)
        self.run('eu5ab_pf_register_start')
        return self.vars[self.ROOT]['eu5ab_pf_serial']

    def observe(self, levels, queue, workers=0):
        self.facts['foundry'].update(building_level=levels,
                                    building_levels_under_construction=queue,
                                    building_employed_amount=workers,
                                    building_employment_size_amount=levels * 1000)
        self.run('eu5ab_refresh_build_pending', self.ROOT)

    def record(self, ident, field):
        return self.variable_maps[self.ROOT].get('eu5ab_pf_c_' + field, {}).get(ident)

    def pending(self, good='tools', kind='output', market='market'):
        prefix = 'eu5ab_build_pending_' if kind == 'output' else 'eu5ab_build_future_input_'
        return self.variable_maps[self.ROOT].get(prefix + good, {}).get(market, 0)

    def deadline(self, ident):
        return self.record(ident, 'deadline')


class ProductionCohortsRuntimeTests(unittest.TestCase):
    def test_sparse_goods_walk_and_load_rebuild_keep_only_actual_recipe_and_credits(self):
        vm = CohortVM()
        ident = vm.start()
        vm.observe(0, 1)
        pending = vm.pending()
        ready = vm.variable_maps[vm.ROOT]['eu5ab_pf_c_goods_ready'][ident]
        self.assertEqual(ready, 1)
        active = {name.removeprefix('eu5ab_pf_c_goods_next_') for name, rows in vm.variable_maps[vm.ROOT].items()
                  if name.startswith('eu5ab_pf_c_goods_next_') and ident in rows}
        self.assertEqual(active, {'tools', 'iron', 'coal'})
        visited = []
        value = vm.value
        def count(expression, stack):
            if isinstance(expression, str):
                found = re.search(r'variable_map\(eu5ab_pf_c_(?:output|input)_(?!credit_)(\w+)\|', expression)
                if found:
                    visited.append(found[1])
            return value(expression, stack)
        vm.value = count
        vm.scopes['eu5ab_pf_id'] = ident
        vm.run('eu5ab_pf_add_reservation', vm.ROOT)
        self.assertEqual(set(visited), active)
        vm.run('eu5ab_pf_rebuild_goods_index', vm.ROOT)
        vm.observe(0, 1)
        self.assertEqual(vm.pending(), pending)
        self.assertEqual(vm.variable_maps[vm.ROOT]['eu5ab_pf_c_goods_ready'][ident], 1)

    def test_one_method_walk_per_building_per_refresh_and_pm_changes_are_observed(self):
        vm = CohortVM()
        vm.start()
        vm.start(queue_before=1)
        walks = []
        execute = vm.execute

        def count_walks(entries, stack):
            if len(entries) == 1 and entries[0][0] == 'every_production_method_of_building':
                walks.append(stack[-1])
            return execute(entries, stack)

        vm.execute = count_walks
        vm.observe(0, 2)
        self.assertEqual(walks, ['foundry'])
        self.assertEqual(vm.pending(), 20)
        vm.active_methods['foundry'] = ['production_method:unknown']
        vm.observe(1, 1)
        self.assertEqual(walks, ['foundry'])
        self.assertEqual(vm.pending(), 0)
        vm.active_methods['foundry'] = list(vm.active_methods['donor'])
        vm.observe(1, 1)
        self.assertEqual(walks, ['foundry', 'foundry'])
        self.assertEqual(vm.pending(), 20)

    def test_native_map_reads_do_not_nest_link_arguments(self):
        from tests import _generated as automation
        # Jomini splits map arguments at every pipe; nested links are rejected
        # even though the offline VM can evaluate them.
        reads = re.findall(r'variable_map\([^"\n]+', automation.generated_fixture().effects)
        self.assertTrue(reads)
        self.assertTrue(all(read.count('|') == 1 and read.count('variable_map(') == 1
                            for read in reads))

    def test_manual_queue_is_never_enrolled(self):
        vm = CohortVM()
        vm.observe(8, 5)
        self.assertEqual(vm.pending(), 0)
        self.assertFalse(vm.lists[vm.ROOT].get('eu5ab_pf_cohorts'))

    def test_known_construction_reservation_never_expires_before_completion(self):
        vm = CohortVM()
        ident = vm.start()
        vm.year += 3
        vm.observe(0, 1)
        self.assertEqual(vm.pending(), 10)
        self.assertEqual(vm.deadline(ident), 0)
        self.assertAlmostEqual(vm.pending('iron', 'input'), 6.5935)

    def test_first_build_completion_releases_by_added_jobs_even_when_starved(self):
        vm = CohortVM()
        ident = vm.start()
        vm.observe(1, 0, 400)
        self.assertEqual(vm.pending(), 6)
        deadline = vm.deadline(ident)
        vm.facts['foundry']['is_opened'] = False
        vm.observe(1, 0, 1000)
        self.assertEqual(vm.pending(), 0)
        self.assertEqual(vm.pending('iron', 'input'), 0)
        self.assertEqual(vm.deadline(ident), deadline)
        vm.observe(1, 0, 0)
        self.assertEqual(vm.pending(), 0)

    def test_expansion_excludes_incumbent_jobs_and_later_manual_levels(self):
        vm = CohortVM()
        ident = vm.start(before=2)
        vm.observe(3, 0, 2250)
        self.assertEqual(vm.record(ident, 'baseline_jobs'), 2000)
        self.assertEqual(vm.pending(), 7.5)
        vm.observe(3, 6, 2500)
        self.assertEqual(vm.pending(), 5)
        vm.observe(9, 0, 2500)
        self.assertEqual(vm.pending(), 5)

    def test_zero_horizon_removes_reservation_and_adds_no_type_cooldown(self):
        vm = CohortVM()
        vm.vars[vm.ROOT]['eu5ab_global_job_fill_deadline_months'] = 0
        ident = vm.start()
        vm.observe(0, 1)
        self.assertEqual(vm.pending(), 10)
        vm.observe(1, 0)
        self.assertIsNone(vm.deadline(ident))
        self.assertEqual(vm.pending(), 0)
        self.assertFalse(vm.variable_maps[vm.ROOT].get('eu5ab_pf_cooldown_iron_foundry'))

    def test_unknown_uses_three_months_and_valid_zero_is_known(self):
        vm = CohortVM()
        vm.vars[vm.ROOT]['eu5ab_global_job_fill_deadline_months'] = 24
        ident = vm.start(known=False)
        vm.active_methods['foundry'] = []
        vm.observe(1, 0)
        deadline = vm.value('eu5ab_pl_today', [vm.ROOT]) + 3 * 31
        self.assertEqual(vm.deadline(ident), deadline)
        self.assertEqual(vm.record(ident, 'known'), 0)
        self.assertEqual(vm.pending(), 0)
        vm.active_methods['foundry'] = list(vm.active_methods['donor'])
        vm.efficiencies['location'] = 0
        # The first valid post-completion reference is accepted as a zero,
        # independently of the earlier unknown and without renewing expiry.
        vm.observe(1, 0)
        self.assertEqual(vm.record(ident, 'known'), 1)
        self.assertEqual(vm.pending(), 0)
        self.assertEqual(vm.deadline(ident), deadline)

    def test_unknown_first_valid_read_and_load_do_not_extend_fallback(self):
        vm = CohortVM()
        ident = vm.start(known=False)
        vm.active_methods['foundry'] = []
        vm.observe(1, 0)
        deadline = vm.deadline(ident)
        restored = deepcopy(vm)
        restored.month_number += 1
        restored.active_methods['foundry'] = list(restored.active_methods['donor'])
        restored.observe(1, 0, 200)
        self.assertEqual(restored.pending(), 8)
        self.assertEqual(restored.deadline(ident), deadline)
        restored.month_number += 2
        restored.observe(1, 0)
        self.assertEqual(restored.pending(), 0)
        self.assertIsNone(restored.deadline(ident))
        restored.observe(1, 2)
        self.assertEqual(restored.pending(), 0)

    def test_batches_keep_independent_completion_dates(self):
        vm = CohortVM()
        first = vm.start()
        second = vm.start(queue_before=1)
        vm.observe(1, 1)
        first_deadline = vm.deadline(first)
        self.assertEqual(vm.deadline(second), 0)
        vm.month_number += 1
        vm.observe(2, 0)
        self.assertEqual(vm.deadline(first), first_deadline)
        self.assertEqual(vm.deadline(second), first_deadline + 31)
        self.assertEqual(vm.record(second, 'baseline_jobs'), 1000)

    def test_completion_deadline_clamps_month_end_and_crosses_year_without_renewal(self):
        for month, horizon, target_month, target_year in ((1, 1, 2, 1436), (12, 2, 2, 1437)):
            with self.subTest(month=month):
                vm = CohortVM()
                vm.month_number, vm.day = month, 31
                vm.vars[vm.ROOT]['eu5ab_global_job_fill_deadline_months'] = horizon
                ident = vm.start()
                vm.observe(1, 0)
                deadline = target_year * 372 + target_month * 31 + 28
                self.assertEqual(vm.deadline(ident), deadline)
                vm.year, vm.month_number, vm.day = target_year, target_month, 27
                vm.observe(1, 0)
                self.assertEqual(vm.deadline(ident), deadline)
                vm.day = 28
                vm.observe(1, 0)
                self.assertIsNone(vm.deadline(ident))

    def test_cancellation_cannot_rebound_into_a_later_manual_project(self):
        vm = CohortVM()
        ident = vm.start()
        vm.observe(0, 0)
        self.assertIsNone(vm.record(ident, 'state'))
        vm.observe(1, 4)
        self.assertEqual(vm.pending(), 0)

    def test_mixed_manual_queue_completes_before_the_registered_mod_unit(self):
        vm = CohortVM()
        ident = vm.start(queue_before=2)
        vm.observe(1, 2)
        self.assertEqual(vm.record(ident, 'state'), 0)
        vm.observe(2, 1)
        self.assertEqual(vm.record(ident, 'state'), 0)
        vm.observe(3, 0)
        self.assertEqual(vm.record(ident, 'state'), 1)
        self.assertEqual(vm.record(ident, 'baseline_jobs'), 2000)
        self.assertEqual(vm.pending(), 10)

    def test_full_employment_keeps_only_the_same_location_type_cooldown(self):
        vm = CohortVM()
        ident = vm.start()
        vm.observe(1, 0, 1000)
        self.assertEqual(vm.pending(), 0)
        self.assertFalse(vm.test('eu5ab_candidate_pending_allowed', '=', 'yes', ['building_type:iron_foundry']))
        self.assertTrue(vm.test('eu5ab_candidate_production_cooldown_clear', '=', 'yes', ['building_type:iron_mill']))
        vm.scopes['eu5ab_candidate_location'] = 'second'
        self.assertTrue(vm.test('eu5ab_candidate_pending_allowed', '=', 'yes', ['building_type:iron_foundry']))
        vm.scopes['eu5ab_candidate_location'] = 'location'
        vm.year += 1
        vm.observe(1, 0, 0)
        self.assertIsNone(vm.deadline(ident))
        self.assertEqual(vm.pending(), 0)

    def test_recipe_switch_removes_obsolete_input_goods_without_renewing_date(self):
        vm = CohortVM()
        vm.building_types['foundry'] = vm.building_types['donor'] = 'building_type:iron_mill'
        model = vm.models['iron_mill']
        vm.active_methods['foundry'] = vm.active_methods['donor'] = ['production_method:' + model.slots[0][0].production_method_id]
        vm.scopes['eu5ab_candidate_building'] = 'building_type:iron_mill'
        vm.vars['building_type:iron_mill'], vm.lists['building_type:iron_mill'] = {}, {}
        ident = vm.start()
        vm.observe(1, 0, 500)
        deadline = vm.deadline(ident)
        self.assertGreater(vm.pending('iron', 'input'), 0)
        vm.active_methods['foundry'] = ['production_method:steel_tools']
        vm.observe(1, 0, 500)
        self.assertEqual(vm.pending('iron', 'input'), 0)
        self.assertGreater(vm.pending('steel', 'input'), 0)
        self.assertEqual(vm.deadline(ident), deadline)

    def test_upgrade_freezes_target_and_old_references_and_compensates_old_supply_loss_once(self):
        vm = CohortVM()
        vm.building_types['foundry'] = vm.building_types['donor'] = 'building_type:iron_mill'
        method = vm.models['iron_mill'].slots[0][0].production_method_id
        vm.active_methods['foundry'] = vm.active_methods['donor'] = ['production_method:' + method]
        vm.scopes['eu5ab_candidate_building'] = 'building_type:iron_mill'
        vm.vars['building_type:iron_mill'], vm.lists['building_type:iron_mill'] = {}, {}
        vm.building_locations['old'] = 'location'
        vm.building_types['old'] = 'building_type:iron_foundry'
        vm.active_methods['old'] = ['production_method:iron_foundry_maintenance']
        vm.vars['old'], vm.lists['old'] = {}, {}
        vm.facts['old'] = dict(building_level=3, building_can_be_upgraded_by=vm.ROOT)
        vm.scopes['eu5ab_engine_replaced_building'] = 'old'
        vm.vars['location'].update(eu5ab_pending_predecessor='old', eu5ab_pending_predecessor_before=3)
        ident = vm.start()
        vm.observe(0, 1)
        self.assertEqual(vm.record(ident, 'output_tools'), 10)
        self.assertEqual(vm.pending(), 10)
        vm.facts['old']['building_level'] = 2
        vm.efficiencies['second'] = 20
        for _ in range(3):
            vm.observe(0, 1)
            self.assertEqual(vm.pending(), 20)
        vm.observe(1, 0, 500)
        self.assertEqual(vm.pending(), 5)
        self.assertEqual(vm.record(ident, 'efficiency'), 5)

    def test_owner_and_market_changes_remove_obsolete_aggregates(self):
        vm = CohortVM()
        ident = vm.start()
        vm.location_markets['location'] = 'other_market'
        vm.observe(0, 1)
        self.assertEqual(vm.pending(), 0)
        self.assertEqual(vm.pending(market='other_market'), 10)
        vm.owners['location'] = 'foreign'
        vm.observe(0, 1)
        self.assertEqual(vm.pending(market='other_market'), 0)
        self.assertIsNone(vm.record(ident, 'state'))

    def test_legacy_fields_cannot_register_projects(self):
        vm = CohortVM()
        vm.lists[vm.ROOT]['eu5ab_pl_tickets'] = [1]
        vm.ledger_set('foundry', 'eu5ab_pl_sample_ready', True)
        vm.lists[vm.ROOT]['eu5ab_pf_projects'] = ['foundry']
        vm.ledger_set('foundry', 'eu5ab_pf_owner', vm.ROOT)
        vm.ledger_set('foundry', 'eu5ab_pf_queued', 9)
        vm.observe(2, 8)
        self.assertEqual(vm.pending(), 0)
        self.assertFalse(vm.lists[vm.ROOT].get('eu5ab_pf_cohorts'))
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_pl_tickets'], [1])


if __name__ == '__main__':
    unittest.main()
