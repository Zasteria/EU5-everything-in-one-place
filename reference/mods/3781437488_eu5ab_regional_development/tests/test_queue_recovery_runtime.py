"""Execute generated queue branches with deterministic native-engine responses."""
import re
import unittest

from src.eu5autobuild.generator import CMM_CANDIDATE_RANKING_ACTUAL_PROFIT
from src.eu5autobuild import annual_budget, building_capacity, construction_slots, project_tracking, queue_bridge, quote_cache, winner_batch
from src.eu5autobuild.food_infrastructure import FOOD_BUILDING_FINAL_GATES
from tests._governor_script_vm import GovernorScriptVM, parse
from tests._automation_runtime import country_counter_initializers
from tests import _generated as automation


class QueueVM(GovernorScriptVM):
    def __init__(self, effects, guis):
        super().__init__({}, {}, {}, {}, (), (), None)
        names = (
            'eu5ab_ensure_template_coverage',
            'eu5ab_sync_location_template_coverage',
            'eu5ab_remove_location_template_coverage',
            'eu5ab_clear_building_capacity',
            'eu5ab_batch_collect_cleanup',
            'eu5ab_capture_building_capacity',
            'eu5ab_clear_validation',
            'eu5ab_clear_quote_production_snapshot',
            'eu5ab_clear_quote_production_values',
            'eu5ab_ensure_validation_inputs',
            'eu5ab_ensure_validation_economics',
            'eu5ab_ensure_validation_materials',
            'eu5ab_commit_candidate_construction_demand',
            'eu5ab_release_candidate_construction_demand',
            'eu5ab_gui_queue_try_profit_candidate',
            'eu5ab_gui_queue_sync_check',
            'eu5ab_gui_queue_try_candidate',
            'eu5ab_record_actual_profit_candidate',
            'eu5ab_record_cached_profit_candidate',
            'eu5ab_gui_capture_candidate_quote',
            'eu5ab_reset_engine_priority_phase_progress',
            'eu5ab_approve_engine_candidate',
            'eu5ab_confirm_engine_candidate',
            'eu5ab_record_confirmed_building',
            'eu5ab_record_queue_start_location',
            'eu5ab_apply_queue_cooldowns',
            'eu5ab_refresh_active_building_type',
            'eu5ab_clear_parallel_capacity',
            'eu5ab_capture_parallel_queue',
            'eu5ab_pf_ensure_maintenance',
            'eu5ab_pf_resume_maintenance',
            'eu5ab_pf_maintain_registered_projects',
            'eu5ab_process_script_rgo_queue',
            'eu5ab_acknowledge_approved_engine_candidate',
            'eu5ab_check_engine_phase_completion',
            'eu5ab_check_engine_confirmation_completion',
            'eu5ab_tick_engine_script_queue',
            'eu5ab_tick_engine_script_confirmation',
            'eu5ab_confirm_requested_engine_candidate',
            'eu5ab_record_requested_engine_fire',
        )
        selected = '\n'.join(automation._blocks_for_token(
            effects + '\n' + guis, '\n' + name + ' = ')[0] for name in names)
        selected = re.sub(r'saved_scopes = \{[^}]*\}', '', selected)
        self.definitions = {k: v for k, _, v in parse(selected)}
        self.definitions.update({k: v for k, _, v in parse(queue_bridge.render_effects(16, 8))})
        self.definitions.update({k: v for k, _, v in parse(quote_cache.render_effects())})
        from tests.test_engine import RULES
        self.definitions.update({k: v for k, _, v in parse(winner_batch.render_effects(RULES))})
        self.definitions.update({k: v for k, _, v in parse(re.sub(r'saved_scopes = \{[^}]*\}', '', winner_batch.render_guis()))})
        for name in ('eu5ab_refresh_approved_cash_quote', 'eu5ab_reserve_engine_candidate'):
            self.definitions[name] = parse(automation._blocks_for_token(effects, '\n' + name + ' = ')[0])[0][2]
        for name in ('eu5ab_prepare_candidate_dependencies', 'eu5ab_retry_waiting_candidate_data',
                     'eu5ab_report_candidate_waiting',
                     'eu5ab_report_candidate_approved', 'eu5ab_report_candidate_confirmed',
                     'eu5ab_report_candidate_rejected'):
            self.definitions.update({k: v for k, _, v in parse(
                automation._blocks_for_token(effects, '\n' + name + ' = ')[0])})
        self.definitions.update({k: v for k, _, v in parse(annual_budget.render_effects())})
        for name in ('eu5ab_recalculate_budget_limit', 'eu5ab_commit_engine_candidate_budget',
                     'eu5ab_release_engine_candidate_reservation'):
            self.definitions[name] = parse(automation._blocks_for_token(effects, '\n' + name + ' = ')[0])[0][2]
        self.capacity_values = {k: v for k, _, v in parse(
            building_capacity.render_values() + building_capacity.render_score_values()
            + building_capacity.phase_values(8))}
        self.capacity_values.update({k: v for k, _, v in parse(annual_budget.render_values())})
        self.capacity_values.update({k: v for k, _, v in parse(quote_cache.render_values())})
        self.capacity_values.update({k: v for k, _, v in parse(winner_batch.render_values())})
        from src.eu5autobuild.queue_dependencies import render_values
        self.capacity_values.update({k: v for k, _, v in parse(render_values())})
        self.capacity_triggers = {k: v for k, _, v in parse(building_capacity.render_triggers())}
        self.capacity_triggers.update({k: v for k, _, v in parse(quote_cache.render_triggers())})
        from src.eu5autobuild import industry_promotion
        industry_effects, industry_triggers, industry_values, _ = industry_promotion.render()
        self.definitions.update({k: v for k, _, v in parse(industry_effects)})
        self.capacity_values.update({k: v for k, _, v in parse(industry_values)})
        self.capacity_triggers.update({k: v for k, _, v in parse(industry_triggers)})
        from tests.test_engine import RULES
        self.capacity_values.update({k: v for k, _, v in parse(
            construction_slots.render()[2] + project_tracking.render(RULES)[2])})
        self.capacity_triggers.update({k: v for k, _, v in parse(
            construction_slots.render()[1] + project_tracking.render(RULES)[1])})
        prices = automation.generated_fixture().values
        self.capacity_values['eu5ab_price_profit_rank'] = parse(
            automation._blocks_for_token(prices, '\neu5ab_price_profit_rank = ')[0])[0][2]
        self.vars.update(location={}, market={}, other_market={})
        self.lists.update(location={}, market={}, other_market={})
        self.owners['location'] = self.ROOT
        self.scopes.update(eu5ab_engine_country=self.ROOT,
                           eu5ab_candidate_location='location',
                           eu5ab_candidate_building='building',
                           eu5ab_engine_capacity_used=0, eu5ab_engine_capacity_limit=100,
                           eu5ab_engine_parallel_modifier=1)
        self.native = {'num_civil_constructions': 0, 'eu5ab_inputs_available': True}
        self.native.update(eu5ab_pl_today=1,
                           eu5ab_candidate_pending_data_ready=True)
        self.native.update({'modifier:max_constructions_at_same_time': 1,
                            'modifier:free_building_levels': 100,
                            'eu5ab_candidate_queued_levels': 0,
                            'eu5ab_output_not_oversupplied': True,
                            'eu5ab_candidate_pending_allowed': True,
                            'eu5ab_candidate_pending_preliminary_allowed': True,
                            'eu5ab_pending_exact_predecessor': False,
                            'eu5ab_candidate_has_direct_output': False,
                            'eu5ab_candidate_route_allowed': True,
                            'eu5ab_has_local_workforce': True,
                            'scope:eu5ab_candidate_building.eu5ab_output_price_factor': 1})
        self.native['scope:eu5ab_candidate_building.eu5ab_candidate_current_labor_factor'] = 1
        self.native['employment_size'] = 100
        self.native.update({gate: True for gate, _ in FOOD_BUILDING_FINAL_GATES})
        # Queue harnesses enter an initialized, valid post-22 monthly phase.
        # Calendar transitions themselves are executed by test_monthly_schedule_runtime.
        self.native['eu5ab_queue_calendar_open'] = True
        self.native['eu5ab_manual_physical_calendar'] = True
        self.native['eu5ab_manual_month_current'] = False
        # Manual-month aliases retain the live values outside a manual month.
        fixture = automation.generated_fixture()
        alias_names = re.findall(r'^(eu5ab_manual_value_\w+) = \{', fixture.values, re.M)
        self.capacity_values.update({k: v for k, _, v in parse('\n'.join(
            automation._blocks_for_token(fixture.values, '\n' + name + ' = ')[0] for name in alias_names))})
        self.maps = {}
        self.variable_maps = {}
        self.market = 'market'
        # Economic ledger behavior is covered by test_rgo_pending_runtime;
        # queue recovery uses only the dispatcher contract of this effect.
        self.stubs = {'eu5ab_pf_confirm_start': lambda: None,
                      'eu5ab_refresh_rgo_pending': lambda: None,
                      'eu5ab_refresh_build_pending': lambda: None}
        self.stubs['eu5ab_ensure_build_pending'] = lambda: None
        # The indexed project registry has its own generated geometry tests.
        self.stubs['eu5ab_pf_refresh_projects'] = lambda: None
        # These boundaries have independent recipe/price runtime tests. Queue
        # fixtures supply their native readings while executing the new gates.
        self.stubs.update({name: lambda: None for name in (
            'eu5ab_prepare_recipe_score_snapshot', 'eu5ab_prepare_candidate_score_snapshot', 'eu5ab_clear_recipe_score_snapshot',
            'eu5ab_clear_native_recipes', 'eu5ab_refresh_native_recipes', 'eu5ab_reserve_candidate_output',
            'eu5ab_prepare_production_reference',
            'eu5ab_pf_capture_start_geometry',
            'eu5ab_release_candidate_output')})
        self.execute(country_counter_initializers(effects), [self.ROOT])
        # Candidate fixtures enter after the scan worker has captured capacity.
        self.vars['location'].update(eu5ab_capacity_used=0, eu5ab_capacity_limit=100,
                                     eu5ab_capacity_ready=1, eu5ab_capacity_open=1,
                                     eu5ab_capacity_factor=1)

    def value(self, x, stack):
        if isinstance(x, list):
            result, matched = 0, False
            for k, op, v in x:
                if k in ('if', 'else_if', 'else'):
                    if k == 'if':
                        matched = False
                    condition = next((value for key, _, value in v if key == 'limit'), [])
                    if not matched and (k == 'else' or self.condition(condition, stack)):
                        body = [entry for entry in v if entry[0] != 'limit']
                        result = self.value([('value', '=', str(result)), *body], stack)
                        matched = True
                elif k == 'switch':
                    fields = {key: value for key, _, value in v}
                    body = fields.get(self.value(fields['trigger'], stack), fields.get('fallback', []))
                    result = self.value([('value', '=', str(result)), *body], stack)
                else:
                    result = self.normalize_arithmetic(
                        super().value([('value', '=', str(result)), (k, op, v)], stack))
            return result
        if isinstance(x, str):
            if x == 'eu5ab_pending_profit_rank':
                return self.value('eu5ab_profit_candidate_rank_value', stack)
            if x in self.native:
                return self.native[x]
            if x == 'eu5ab_candidate_completed_levels':
                return self.native.get('location_building_level(scope:eu5ab_candidate_building)', 0)
            if x in self.capacity_values:
                return self.value(self.capacity_values[x], stack)
            if '.' in x and x.rsplit('.', 1)[1] in self.capacity_values:
                scope, name = x.rsplit('.', 1)
                return self.value(name, stack + [self.target(scope, stack)])
            if x == 'scope:eu5ab_candidate_location.eu5ab_engine_adjusted_profit':
                # Ordinary candidates are unchanged; food tests inject the value
                # evaluated by FoodVM from the generated arithmetic definitions.
                return self.scopes.get('eu5ab_engine_profit')
            match = re.fullmatch(r'global_variable_map\(([^|]+)\|scope:([^)]*)\)', x)
            if match:
                return self.maps.get(match[1], {}).get(self.scopes[match[2]], 0)
            if x.startswith('location_building_level('):
                return self.native.get(x, 0)
            if x == 'eu5ab_candidate_completed_levels':
                return self.native.get('location_building_level(scope:eu5ab_candidate_building)', 0)
            if x.startswith('variable_map('):
                name, key = x[len('variable_map('):-1].split('|', 1)
                return self.variable_maps.get(stack[-1], {}).get(name, {}).get(self.value(key, stack))
        return super().value(x, stack)

    def normalize_arithmetic(self, number):
        return number

    def target(self, word, stack):
        if word == 'market':
            return self.market
        return super().target(word, stack)

    def test(self, k, op, v, stack):
        data = dict((a, c) for a, _, c in v) if isinstance(v, list) else {}
        if k in self.capacity_triggers:
            return self.condition(self.capacity_triggers[k], stack) == (v == 'yes')
        if k == 'OR':
            return any(self.test(*entry, stack) for entry in v)
        if k in ('AND', 'NOT'):
            result = all(self.test(*entry, stack) for entry in v)
            return not result if k == 'NOT' else result
        if k in ('owner', 'building_type') and isinstance(v, list):
            target = self.target(k, stack)
            return target is not None and self.condition(v, stack + [target])
        if k == 'exists':
            return self.value(v, stack) is not None
        if k == 'is_target_in_variable_list':
            return self.value(data['target'], stack) in self.lists[stack[-1]].get(data['name'], [])
        if k == 'has_global_variable_map':
            return bool(self.maps.get(v))
        if k == 'has_variable_list':
            return bool(self.lists[stack[-1]].get(v))
        if k == 'any_owned_location':
            return any(self.condition(v, stack + [location])
                       for location, owner in self.owners.items() if owner == stack[-1])
        if k == 'any_in_list':
            condition = [entry for entry in v if entry[0] != 'variable']
            return any(self.condition(condition, stack + [item])
                       for item in self.lists[stack[-1]].get(data['variable'], []))
        if k == 'is_key_in_global_variable_map':
            return self.value(data['target'], stack) in self.maps.get(data['name'], {})
        if k == 'has_variable_map':
            return bool(self.variable_maps.get(stack[-1], {}).get(v))
        if k == 'is_key_in_variable_map':
            return self.value(data['target'], stack) in self.variable_maps.get(stack[-1], {}).get(data['name'], {})
        if k in ('eu5ab_candidate_replaces_existing_building',
                 'eu5ab_candidate_is_expansion'):
            return self.native.get(k, False) == (v == 'yes')
        return super().test(k, op, v, stack)

    def execute(self, entries, stack):
        # Delegate whole if/else chains, retaining the shared interpreter's semantics.
        index = 0
        while index < len(entries):
            k, _, v = entries[index]
            end = index + 1
            if k == 'if':
                while end < len(entries) and entries[end][0] in ('else_if', 'else'):
                    end += 1
            data = dict((a, c) for a, _, c in v) if isinstance(v, list) else {}
            if k in self.stubs:
                self.stubs[k]()
            elif k in ('owner', 'market'):
                self.execute(v, stack + [self.target(k, stack)])
            elif k == 'remove_from_global_variable_map':
                self.maps.setdefault(data['name'], {}).pop(self.value(data['key'], stack), None)
            elif k == 'add_to_global_variable_map':
                self.maps.setdefault(data['name'], {})[self.value(data['key'], stack)] = self.value(data['value'], stack)
            elif k == 'clear_global_variable_map':
                self.maps.pop(v, None)
            elif k == 'add_to_variable_map':
                entity_maps = self.variable_maps.setdefault(stack[-1], {})
                entity_maps.setdefault(data['name'], {})[
                    self.value(data['key'], stack)
                ] = self.value(data['value'], stack)
            elif k == 'remove_from_variable_map':
                self.variable_maps.setdefault(stack[-1], {}).setdefault(data['name'], {}).pop(self.value(data['key'], stack), None)
            elif k == 'clear_variable_map':
                self.variable_maps.setdefault(stack[-1], {}).pop(v, None)
            else:
                super().execute(entries[index:end], stack)
            index = end

    def run(self, name, root='location'):
        body = self.definitions[name]
        if name.startswith('eu5ab_gui_'):
            body = dict((k, v) for k, _, v in body)['effect']
        self.execute(body, [root])


def profit_queue_vm():
    fixture = automation.generated_fixture()
    vm = QueueVM(fixture.effects, fixture.scripted_guis)
    vm.vars[vm.ROOT].update(eu5ab_q_active=1, eu5ab_q_phase=5,
                           eu5ab_q_profit_selecting=1, eu5ab_q_approved=0,
                           eu5ab_monthly_build_quota=3,
                           eu5ab_constructions_started_this_tick=0)
    vm.lists['location']['eu5ab_q_profit_best_types'] = ['building']
    vm.scopes['eu5ab_engine_can_build'] = True
    vm.scopes['eu5ab_engine_queue_check_stage'] = 0
    vm.scopes['eu5ab_engine_cost'] = 100
    vm.native['scope:eu5ab_candidate_building.eu5ab_recipe_expected_output_value'] = 1
    for name in ('in_current_priority_phase', 'passes_selected_metric',
                 'has_actual_budget', 'keeps_actual_cash_reserve'):
        vm.native['eu5ab_engine_candidate_' + name] = True
    vm.native['eu5ab_engine_construction_materials_available'] = True
    vm.native['eu5ab_engine_candidate_has_emergency_demand'] = False
    vm.stubs['eu5ab_approve_engine_candidate'] = lambda: vm.vars['location'].update(eu5ab_q_location_approved=1)
    return vm


class QueueRecoveryRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = automation.generated_fixture().effects
        cls.guis = automation.generated_fixture().scripted_guis

    def vm(self):
        return QueueVM(self.effects, self.guis)

    def profit_vm(self):
        return profit_queue_vm()

    def test_rejected_profit_winner_requests_bounded_retry(self):
        for gate in ('has_actual_budget', 'keeps_actual_cash_reserve', 'passes_selected_metric'):
            with self.subTest(gate=gate):
                vm = self.profit_vm()
                vm.native['eu5ab_engine_candidate_' + gate] = False
                vm.run('eu5ab_gui_queue_try_profit_candidate')
                self.assertEqual(vm.lists['location']['eu5ab_q_failed_types'], ['building'])
                self.assertTrue(vm.vars[vm.ROOT]['eu5ab_q_retry_phase'])
                # A repeated GUI callback must not count or exclude the winner twice.
                vm.run('eu5ab_gui_queue_try_profit_candidate')
                self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_processed'], 1)

    def test_recipe_became_short_before_final_validation_rejects_and_retries(self):
        vm = self.profit_vm()
        vm.native['eu5ab_inputs_available'] = False
        vm.run('eu5ab_gui_queue_try_profit_candidate')
        self.assertNotIn('eu5ab_q_location_approved', vm.vars['location'])
        self.assertEqual(vm.lists['location']['eu5ab_q_failed_types'], ['building'])
        self.assertTrue(vm.vars[vm.ROOT]['eu5ab_q_retry_phase'])

    def test_food_need_disappears_before_approval_in_both_ranking_modes(self):
        from itertools import product
        for callback, (gate, counter) in product(
            ('eu5ab_gui_queue_try_candidate', 'eu5ab_gui_queue_try_profit_candidate'), FOOD_BUILDING_FINAL_GATES,
        ):
            with self.subTest(callback=callback, gate=gate):
                vm = self.profit_vm()
                if callback == 'eu5ab_gui_queue_try_candidate':
                    vm.vars[vm.ROOT].pop('eu5ab_q_profit_selecting', None)
                    vm.scopes['eu5ab_engine_queue_check_stage'] = 5
                    vm.vars[vm.ROOT]['eu5ab_global_candidate_ranking_mode'] = 1
                    vm.lists['location']['eu5ab_q_phase_5_types'] = ['building']
                vm.native[gate] = False
                vm.run(callback)
                self.assertNotIn('eu5ab_q_location_approved', vm.vars['location'])
                self.assertEqual(vm.vars[vm.ROOT][counter], 1)
                if callback.endswith('profit_candidate'):
                    self.assertTrue(vm.vars[vm.ROOT]['eu5ab_q_retry_phase'])
                vm.run(callback)
                self.assertEqual(vm.vars[vm.ROOT][counter], 1)

    def test_approved_winner_and_full_quota_do_not_retry(self):
        for full in (False, True):
            vm = self.profit_vm()
            if full:
                vm.vars[vm.ROOT]['eu5ab_q_approved'] = 3
            vm.run('eu5ab_gui_queue_try_profit_candidate')
            self.assertNotIn('eu5ab_q_retry_phase', vm.vars[vm.ROOT])
            self.assertEqual('eu5ab_q_location_approved' in vm.vars['location'], not full)

    def test_retry_selects_affordable_runner_up_instead_of_failed_winner(self):
        vm = self.profit_vm()
        vm.native['eu5ab_engine_candidate_has_actual_budget'] = False
        vm.run('eu5ab_gui_queue_try_profit_candidate')
        vm.lists[vm.ROOT]['eu5ab_q_phase_5_locations'] = ['location']
        vm.lists['location']['eu5ab_q_phase_5_types'] = ['building', 'cheaper']
        vm.stubs['eu5ab_reset_engine_candidate_watchdog_progress'] = lambda: None
        vm.run('eu5ab_reset_engine_priority_phase_progress', vm.ROOT)
        vm.scopes['eu5ab_engine_queue_check_stage'] = 5
        self.assertEqual(vm.lists['location']['eu5ab_q_failed_types'], ['building'])
        vm.vars[vm.ROOT]['eu5ab_global_candidate_ranking_mode'] = CMM_CANDIDATE_RANKING_ACTUAL_PROFIT
        vm.native['scope:eu5ab_candidate_building.eu5ab_current_candidate_configured_priority'] = 1
        # Engine responses model the same remaining budget: 500 is unaffordable,
        # while 100 still fits. The rejected winner has the higher profit.
        for building, affordable, profit in [('building', False, 20), ('cheaper', True, 5)]:
            vm.scopes['eu5ab_candidate_building'] = building
            vm.scopes['eu5ab_engine_profit'] = profit
            vm.native['eu5ab_engine_candidate_has_actual_budget'] = affordable
            vm.run('eu5ab_gui_queue_try_candidate')
        self.assertEqual(vm.lists['location']['eu5ab_q_profit_best_types'], ['cheaper'])

    def test_current_worker_penalty_changes_rank_without_changing_true_profit(self):
        for profit in (10, -10):
            for factor in (1, .4):
                vm = self.vm()
                vm.scopes['eu5ab_engine_profit'] = profit
                vm.native['scope:eu5ab_candidate_building.eu5ab_current_candidate_configured_priority'] = 1
                vm.native['scope:eu5ab_candidate_building.eu5ab_candidate_current_labor_factor'] = factor
                # QueueVM already supplies the post-scan capacity snapshot.
                vm.run('eu5ab_record_actual_profit_candidate')
                rank = abs(profit) * .01 + profit
                expected = rank * factor if rank >= 0 else rank / factor
                self.assertAlmostEqual(vm.vars['location']['eu5ab_q_profit_best_rank'], expected)
                self.assertEqual(vm.vars['location']['eu5ab_q_profit_best_actual'], profit)

    def test_failed_construction_releases_materials_through_confirmation(self):
        vm = self.vm()
        goods = re.findall(r'name = eu5ab_new_committed_(\w+) value', self.effects)
        for good in goods:
            vm.native[f'scope:eu5ab_candidate_building.eu5ab_construction_demand_{good}'] = 4
        vm.run('eu5ab_commit_candidate_construction_demand')
        vm.vars['location']['eu5ab_q_queue_before'] = 0
        vm.stubs['eu5ab_release_engine_candidate_reservation'] = lambda: vm.calls.append('refund')
        vm.run('eu5ab_confirm_engine_candidate')
        self.assertEqual(vm.calls, ['refund'])
        self.assertTrue(vm.vars[vm.ROOT]['eu5ab_q_retry_phase'])
        self.assertNotIn('eu5ab_q_material_market', vm.vars['location'])
        for good in goods:
            self.assertEqual(vm.maps[f'eu5ab_q_market_committed_{good}']['market'], 0)

    def test_build_kind_is_snapshotted_before_construction_and_confirmed(self):
        cases = (
            (False, False, 3),  # First construction of this type.
            (False, True, 4),   # Another level of the same building type.
            (True, False, 2),   # Replacement upgrade to a successor type.
        )
        for replacement, expansion, expected in cases:
            with self.subTest(expected=expected):
                vm = self.vm()
                vm.native.update(
                    eu5ab_candidate_replaces_existing_building=replacement,
                    eu5ab_candidate_is_expansion=expansion,
                    num_civil_constructions=0,
                )
                vm.scopes.update(
                    eu5ab_engine_cost=40,
                    eu5ab_engine_income=2,
                    eu5ab_engine_profit=1,
                )
                vm.stubs['eu5ab_reserve_engine_candidate'] = lambda: None
                vm.stubs['eu5ab_commit_candidate_construction_demand'] = lambda: None
                vm.run('eu5ab_approve_engine_candidate')
                self.assertEqual(
                    vm.vars['location']['eu5ab_q_approved_build_kind'], expected
                )

                # The native construction may make a new building look like an
                # expansion. Confirmation must use the pre-construction snapshot.
                vm.native['eu5ab_candidate_is_expansion'] = True
                vm.native['num_civil_constructions'] = 1
                vm.native['eu5ab_candidate_queued_levels'] = 1
                vm.vars['location']['eu5ab_q_fire_issued'] = 1
                vm.stubs['eu5ab_commit_engine_candidate_budget'] = lambda: None
                vm.run('eu5ab_confirm_engine_candidate')
                self.assertEqual(
                    vm.vars[vm.ROOT]['eu5ab_diag_last_build_kind'], expected
                )

    def test_retry_with_no_approvals_does_not_advance_phase(self):
        vm = self.profit_vm()
        vm.vars[vm.ROOT].update(eu5ab_q_retry_phase=1, eu5ab_q_processed=1,
                               eu5ab_q_expected=1, eu5ab_q_seen=0,
                               eu5ab_q_progress_last=0, eu5ab_q_stall_rounds=0,
                               eu5ab_global_candidate_ranking_mode=CMM_CANDIDATE_RANKING_ACTUAL_PROFIT)
        vm.stubs['eu5ab_restart_engine_priority_phase'] = lambda: vm.calls.append('retry')
        vm.stubs['eu5ab_advance_engine_priority_phase'] = lambda: vm.calls.append('advance')
        vm.run('eu5ab_gui_queue_sync_check', vm.ROOT)
        self.assertEqual(vm.calls, ['retry'])

    def test_release_materials_preserves_other_approvals_and_original_market(self):
        vm = self.vm()
        goods = re.findall(r'name = eu5ab_new_committed_(\w+) value', self.effects)
        self.assertTrue(goods)
        for good in goods:
            vm.native[f'scope:eu5ab_candidate_building.eu5ab_construction_demand_{good}'] = 4
        vm.run('eu5ab_commit_candidate_construction_demand')
        vm.run('eu5ab_commit_candidate_construction_demand')
        vm.market = 'other_market'
        vm.run('eu5ab_release_candidate_construction_demand')
        for good in goods:
            self.assertEqual(vm.maps[f'eu5ab_q_market_committed_{good}'], {'market': 4})

    def test_missing_data_is_retained_without_failure_cooldown_or_busy_retry(self):
        vm = self.profit_vm()
        vm.vars[vm.ROOT].update(eu5ab_q_expected=1, eu5ab_q_processed=0,
                               eu5ab_q_progress_last=0, eu5ab_q_stall_rounds=0,
                               eu5ab_q_data_day=1, eu5ab_q_data_commits=0)
        vm.native['eu5ab_candidate_pending_data_ready'] = False
        vm.run('eu5ab_gui_queue_try_profit_candidate')
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_waiting_data'], 1)
        self.assertEqual(vm.lists['location']['eu5ab_q_waiting_types'], ['building'])
        self.assertFalse(vm.lists['location'].get('eu5ab_q_failed_types'))
        self.assertNotIn('eu5ab_failure_cooldown', vm.vars['location'])
        vm.stubs['eu5ab_finish_engine_candidate_queue'] = lambda: self.fail('data wait was discarded')
        vm.stubs['eu5ab_advance_engine_priority_phase'] = lambda: self.fail('priority was skipped')
        vm.stubs['eu5ab_restart_engine_priority_phase'] = lambda: vm.calls.append('retry')
        for _ in range(30):
            vm.run('eu5ab_gui_queue_sync_check', vm.ROOT)
        self.assertEqual(vm.calls, [])
        vm.native['eu5ab_pl_today'] = 2
        vm.run('eu5ab_retry_waiting_candidate_data', vm.ROOT)
        self.assertEqual(vm.calls, ['retry'])

    def test_ready_approval_can_fire_while_another_candidate_waits(self):
        vm = self.profit_vm()
        vm.vars[vm.ROOT].update(eu5ab_q_expected=1, eu5ab_q_processed=0,
                               eu5ab_q_progress_last=0, eu5ab_q_stall_rounds=0,
                               eu5ab_q_data_day=1, eu5ab_q_data_commits=0)
        vm.vars[vm.ROOT].update(eu5ab_q_waiting_data=1, eu5ab_q_processed=2,
                               eu5ab_q_expected=2, eu5ab_q_approved=1, eu5ab_q_seen=1)
        vm.lists[vm.ROOT]['eu5ab_pl_tickets'] = [99]
        vm.run('eu5ab_gui_queue_sync_check', vm.ROOT)
        self.assertTrue(vm.vars[vm.ROOT]['eu5ab_q_fire'])


if __name__ == '__main__':
    unittest.main()
