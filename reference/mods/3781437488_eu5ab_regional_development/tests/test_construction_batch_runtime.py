"""Execute generated batch control flow with injected native construction.

Treasury precision, ordering, reservations and stale receipts are real script
branches. Native costs/queue mutations are fixtures, not game acceptance.
"""
from copy import deepcopy
from decimal import Decimal
import re
import unittest

from src.eu5autobuild import construction_batch as batch
from src.eu5autobuild.script_syntax import parse as syntax_parse
from tests._generated import generated_fixture, _blocks_for_token
from tests._governor_script_vm import parse
from tests.test_queue_bridge_runtime import BridgeVM


class BatchVM(BridgeVM):
    def __init__(self):
        super().__init__()
        f = generated_fixture()
        names = re.findall(r'^(eu5ab_(?:batch_\w+|dispatch_construction_batch|dispatch_queue_bridge)) = \{', f.effects, re.M)
        source = '\n'.join(_blocks_for_token(f.effects, '\n' + name + ' = ')[0] for name in names)
        source += _blocks_for_token(f.scripted_guis, '\neu5ab_gui_batch_capture_cost = ')[0]
        source = re.sub(r'saved_scopes = \{[^}]*\}', '', source)
        self.definitions.update({k: v for k, _, v in parse(source)})
        names = re.findall(r'^(eu5ab_batch_\w+) = \{', f.values, re.M)
        self.capacity_values.update({k: v for k, _, v in parse('\n'.join(
            _blocks_for_token(f.values, '\n' + name + ' = ')[0] for name in names))})
        self.year = 1436
        self.vars[self.ROOT].update(eu5ab_batch_schema=1, eu5ab_batch_ranking_mode=0, eu5ab_global_budget_mode=1,
            eu5ab_global_fixed_annual_budget=10000, eu5ab_global_budget_limit=10000,
            eu5ab_global_budget_spent=0, eu5ab_global_budget_remaining=10000,
            eu5ab_budget_year=1436, eu5ab_global_candidates_per_location=3,
            eu5ab_global_actual_profit_candidates_per_location=10)
        self.cash = Decimal('1000.12345')
        self.commands = []
        self.debits = {}
        self.failures = set()
        self.queues = {}
        self.provinces = {}
        self.markets = {}
        self.slot_limits = {}
        self.stubs['eu5ab_batch_update_market_scores'] = lambda: None
        # Phase fixtures enter after native screening. Cost transport and
        # physical dispatch below still execute their generated branches.
        self.stubs['eu5ab_request_candidate_quotes'] = lambda: None
        # Geometry has an independent instance/cohort harness. The batch tests
        # retain real type-count enrollment and per-command queue baselines.
        self.native['eu5ab_engine_adjusted_profit'] = Decimal(10)
        # Price/recipe ranking is an injected boundary for identity tests;
        # shared ledger arithmetic is exercised independently below.
        self.native.update(eu5ab_candidate_pending_factor=1, eu5ab_current_candidate_score=10)
        for name in ('eu5ab_report_candidate_confirmed', 'eu5ab_clear_recipe_score_snapshot'):
            self.stubs[name] = lambda: None
        self.stubs['eu5ab_finish_engine_candidate_queue'] = lambda: self.vars[self.ROOT].pop('eu5ab_q_active', None)
        self.stubs['eu5ab_advance_engine_priority_phase'] = self.advance_phase

    def advance_phase(self):
        self.vars[self.ROOT]['eu5ab_q_phase'] += 1
        if self.vars[self.ROOT]['eu5ab_q_phase'] > 16:
            self.vars[self.ROOT].pop('eu5ab_q_active', None)

    def target(self, word, stack):
        if word.endswith('.owner'):
            return self.owners.get(self.target(word[:-6], stack))
        if word.endswith('.market'):
            return self.markets.get(super().target(word[:-7], stack), 'market')
        if word.endswith('.province'):
            return self.provinces.get(super().target(word[:-9], stack), 'province')
        if word == 'province':
            return self.provinces.get(stack[-1], 'province')
        if word == 'market':
            return self.markets.get(stack[-1], 'market')
        if '.variable_map(' in word or word.startswith('variable_map('):
            return self.value(word, stack)
        return super().target(word, stack)

    def value(self, x, stack):
        if isinstance(x, str):
            if x == 'modifier:max_constructions_at_same_time':
                return self.slot_limits.get(stack[-1], 3)
            if x == 'num_civil_constructions':
                return sum(n for (location, _), n in self.queues.items() if location == stack[-1])
            if x == 'gold' or x == 'owner.gold':
                return self.cash
            if x == 'market':
                return self.target(x, stack)
            if x == 'province' or x.endswith(('.market', '.province')):
                return self.target(x, stack)
            if '.' in x and x.rsplit('.', 1)[1] in self.native:
                scope, name = x.rsplit('.', 1)
                return self.value(name, stack + [self.target(scope, stack)])
            if '.variable_map(' in x:
                scope, formula = x.split('.variable_map(', 1)
                return self.value('variable_map(' + formula, stack + [self.target(scope, stack)])
            if x == 'eu5ab_candidate_queued_levels':
                return self.queues.get((stack[-1], self.scopes['eu5ab_candidate_building']), 0)
            if x == 'eu5ab_candidate_completed_levels':
                return 1
            if x.startswith('goods:') or x.startswith('building_type:'):
                return x
        return super().value(x, stack)

    def test(self, k, op, v, stack):
        if ('variable_map(' in k) and isinstance(v, list):
            return self.condition(v, stack + [self.value(k, stack)])
        if k == 'trigger_if':
            condition = next(x for name, _, x in v if name == 'limit')
            return not self.condition(condition, stack) or self.condition(
                [e for e in v if e[0] != 'limit'], stack)
        return super().test(k, op, v, stack)

    def execute(self, entries, stack):
        index = 0
        while index < len(entries):
            k, _, v = entries[index]
            end = index + 1
            if k == 'if':
                while end < len(entries) and entries[end][0] in ('else_if', 'else'):
                    end += 1
            if k == 'construct_building':
                data = {a: b for a, _, b in v}
                kind = self.value(data['building_type'], stack)
                project = self.scopes['eu5ab_batch_id']
                self.commands.append((project, stack[-1], kind, self.cash))
                if kind not in self.failures:
                    self.cash -= self.debits.get(kind, Decimal('100.12345'))
                    key = (stack[-1], kind)
                    self.queues[key] = self.queues.get(key, 0) + 1
            elif k == 'province':
                self.execute(v, stack + [self.target(k, stack)])
            elif k.startswith('variable_map(') or '.variable_map(' in k:
                self.execute(v, stack + [self.target(k, stack)])
            else:
                super().execute(entries[index:end], stack)
            index = end

    def add(self, kind, score, cost='100.12345', *, location='location', slots=10,
            province='province', market='market', build_kind=3, material=0):
        self.owners[location] = self.ROOT
        self.vars.setdefault(location, {})
        self.slot_limits.setdefault(location, slots)
        self.lists.setdefault(location, {})
        self.run('eu5ab_batch_slots_ensure', location)
        self.provinces[location] = province
        self.markets[location] = market
        self.scopes.update(eu5ab_candidate_location=location, eu5ab_candidate_building=kind,
                           eu5ab_batch_market=market, eu5ab_batch_province=province)
        maps = self.variable_maps.setdefault(location, {})
        for field, value in dict(score=score, cost=Decimal(cost), kind=build_kind, pending_open=1,
                                 adjusted_profit=10, material_lumber=material, market=market,
                                 province=province, ledger_generation=0).items():
            maps.setdefault('eu5ab_quote_' + field, {})[kind] = value
        self.run('eu5ab_batch_add_candidate', self.ROOT)
        project = self.scopes['eu5ab_batch_id']
        return project

    def field(self, field, project):
        return self.variable_maps[self.ROOT]['eu5ab_batch_' + field][project]

    def drain(self):
        self.run('eu5ab_batch_approve', self.ROOT)
        approved = self.lists[self.ROOT]['eu5ab_batch_approved'][:]
        self.run('eu5ab_batch_issue', self.ROOT)
        return approved


class ConstructionBatchTests(unittest.TestCase):
    def backfill_vm(self, *, enabled=True, mode=0, count=7, location='location'):
        vm = BatchVM()
        vm.vars[vm.ROOT].update(eu5ab_global_candidates_per_location=1,
                               eu5ab_global_actual_profit_candidates_per_location=1,
                               eu5ab_batch_ranking_mode=mode)
        if enabled:
            vm.vars[vm.ROOT]['eu5ab_scan_backfill_enabled'] = 1
        types = [f'candidate_{i}' for i in range(count)]
        for i, kind in enumerate(types):
            vm.add(kind, count - i, location=location)
        vm.lists[vm.ROOT]['eu5ab_batch_pool'] = []
        vm.lists[vm.ROOT]['eu5ab_q_phase_5_locations'] = [location]
        vm.lists[location]['eu5ab_q_phase_5_types'] = types[:]
        vm.lists[location]['eu5ab_batch_screened_types'] = types[:]
        vm.lists[location]['eu5ab_batch_passed_types'] = types[:]
        vm.failures.update(types)
        return vm, types

    def test_native_shortlist_backfill_is_opt_in_bounded_and_stops_after_success(self):
        for enabled, mode, success, expected in (
            (False, 0, None, 1), (True, 0, None, 3),
            (True, 2, None, 6), (True, 0, 1, 2), (True, 0, 0, 1),
        ):
            with self.subTest(enabled=enabled, mode=mode, success=success):
                vm, types = self.backfill_vm(enabled=enabled, mode=mode)
                if success is not None:
                    vm.failures.remove(types[success])
                vm.run('eu5ab_dispatch_construction_batch', vm.ROOT)
                self.assertEqual([row[2] for row in vm.commands], types[:expected])
                self.assertEqual(vm.vars[vm.ROOT].get('eu5ab_diag_backfill_checked', 0), expected - 1)
                self.assertEqual(vm.vars[vm.ROOT].get('eu5ab_diag_backfill_stage_failed', 0),
                                 expected - 1 if success is None else 0)
                self.assertEqual(vm.vars[vm.ROOT]['eu5ab_global_budget_spent'],
                                 Decimal('100.12345') if success is not None else 0)
                self.assertEqual(vm.vars[vm.ROOT].get('eu5ab_batch_reserved', 0), 0)

    def test_reload_preserves_primary_identities_and_consumed_backfill_budget(self):
        vm, types = self.backfill_vm()
        vm.scopes['eu5ab_engine_country'] = vm.ROOT
        vm.run('eu5ab_batch_prepare_phase', vm.ROOT)
        vm.drain()
        vm.lists[vm.ROOT]['eu5ab_batch_pool'] = []
        vm.run('eu5ab_batch_try_backfill', vm.ROOT)
        self.assertEqual(vm.vars['location']['eu5ab_batch_backfill_remaining'], 1)
        vm.run('eu5ab_batch_resume', vm.ROOT)
        vm.run('eu5ab_dispatch_construction_batch', vm.ROOT)
        self.assertEqual([row[2] for row in vm.commands], types[:3])
        self.assertEqual(vm.vars['location']['eu5ab_batch_backfill_remaining'], 0)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_diag_backfill_checked'], 2)

    def test_backfill_budget_is_shared_across_phases_and_foreign_locations_are_skipped(self):
        vm, types = self.backfill_vm()
        vm.scopes['eu5ab_engine_country'] = vm.ROOT
        vm.run('eu5ab_batch_prepare_phase', vm.ROOT)
        vm.vars['location']['eu5ab_batch_backfill_remaining'] = 1
        vm.vars[vm.ROOT]['eu5ab_q_phase'] = 6
        vm.lists[vm.ROOT]['eu5ab_q_phase_6_locations'] = ['location']
        vm.lists['location']['eu5ab_q_phase_6_types'] = types[3:]
        vm.run('eu5ab_dispatch_construction_batch', vm.ROOT)
        self.assertEqual([row[2] for row in vm.commands], types[3:5])
        vm, _ = self.backfill_vm()
        vm.scopes['eu5ab_engine_country'] = vm.ROOT
        vm.run('eu5ab_batch_prepare_phase', vm.ROOT)
        vm.lists[vm.ROOT]['eu5ab_batch_pool'] = []
        vm.owners['location'] = 'foreign'
        vm.run('eu5ab_batch_try_backfill', vm.ROOT)
        self.assertEqual(vm.commands, [])
        self.assertEqual(vm.vars['location']['eu5ab_batch_backfill_remaining'], 2)

    def test_queue_cleanup_visits_each_location_once_across_all_indexes(self):
        vm = BatchVM()
        vm.add('a', 10)
        for index in ('eu5ab_quote_locations', 'eu5ab_q_approved_locations',
                      'eu5ab_q_profit_locations', 'eu5ab_q_phase_1_locations',
                      'eu5ab_q_phase_5_unsorted_locations', 'eu5ab_q_phase_8_rgo_locations'):
            vm.lists[vm.ROOT][index] = ['location']
        cleared = []
        vm.stubs['eu5ab_apply_queue_cooldowns'] = lambda: None
        execute = vm.execute
        def count(entries, stack):
            if len(entries) == 1 and entries[0][0] == 'eu5ab_clear_location_candidate_state':
                cleared.append(stack[-1])
            return execute(entries, stack)
        vm.execute = count
        vm.run('eu5ab_clear_engine_candidate_queue', vm.ROOT)
        self.assertEqual(cleared, ['location'])
        self.assertEqual(vm.vars['location']['eu5ab_batch_slots'], 10)

    def test_batch_native_calls_precede_next_batch_and_debits_settle_once(self):
        vm = BatchVM()
        a = vm.add('a', 10)
        b = vm.add('b', 20)
        vm.debits.update(a=Decimal('110.54321'), b=Decimal('90.01234'))
        self.assertEqual(vm.drain(), [b, a])
        self.assertEqual([c[2] for c in vm.commands], ['b', 'a'])
        self.assertEqual(vm.field('debit', a), Decimal('110.54321'))
        self.assertEqual(vm.field('debit', b), Decimal('90.01234'))
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_global_budget_spent'], Decimal('200.55555'))
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_constructions_started_this_tick'], 2)
        before = deepcopy((vm.vars, vm.variable_maps, vm.commands, vm.cash))
        vm.run('eu5ab_batch_issue', vm.ROOT)
        vm.run('eu5ab_batch_confirm', vm.ROOT)
        self.assertEqual((vm.vars, vm.variable_maps, vm.commands, vm.cash), before)

    def test_actual_debit_exhausts_budget_inside_preapproved_batch(self):
        vm = BatchVM()
        vm.vars[vm.ROOT].update(eu5ab_global_budget_limit=150, eu5ab_global_budget_remaining=150)
        a = vm.add('a', 30, '40')
        b = vm.add('b', 20, '40')
        c = vm.add('c', 10, '40')
        vm.debits.update(a=Decimal(160))
        self.assertEqual(vm.drain(), [a, b, c])
        self.assertEqual([r[2] for r in vm.commands], ['a'])
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_global_budget_spent'], 160)
        self.assertEqual(vm.field('status', b), 7)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_batch_reserved'], 0)

    def test_boundary_approves_single_overshoot_and_failure_releases(self):
        vm = BatchVM()
        vm.vars[vm.ROOT].update(eu5ab_global_budget_limit=50, eu5ab_global_budget_remaining=50)
        a = vm.add('a', 20)
        b = vm.add('b', 10)
        self.assertEqual(vm.drain(), [a])
        self.assertEqual(vm.field('status', b), 1)
        self.assertEqual(len(vm.commands), 1)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_global_budget_remaining'], 0)

    def test_unaffordable_candidate_does_not_block_cheaper_row_or_cash_floor(self):
        vm = BatchVM()
        vm.cash = Decimal('150.12345')
        vm.add('expensive', 30, '101')
        cheap = vm.add('cheap', 20, '100')
        vm.debits['cheap'] = Decimal(100)
        self.assertEqual(vm.drain(), [cheap])
        self.assertEqual(vm.cash, Decimal('50.12345'))
        self.assertEqual(len(vm.commands), 1)

    def test_shared_material_and_granary_reservations_are_released_on_failure(self):
        vm = BatchVM()
        rootmaps = vm.variable_maps.setdefault(vm.ROOT, {})
        rootmaps['eu5ab_batch_material_lumber'] = {'market': 15}
        rootmaps['eu5ab_batch_price_lumber'] = {'market': 1}
        a = vm.add('a', 30, material=10)
        b = vm.add('b', 20, location='second', material=10)
        vm.failures.add('a')
        self.assertEqual(vm.drain(), [a])
        self.assertEqual(rootmaps['eu5ab_batch_material_lumber']['market'], 15)
        self.assertEqual(vm.vars['location']['eu5ab_batch_slots'], 10)
        self.assertEqual(vm.field('status', a), 5)
        self.assertEqual(vm.field('status', b), 1)
        # Either granary blocks the other type in the same province. Failure
        # releases that reservation, while a successful project retains it.
        for first_type, second_type in (('granary', 'village_granary'),
                                        ('village_granary', 'granary')):
            with self.subTest(first_type=first_type):
                vm = BatchVM()
                first_type, second_type = ('building_type:' + first_type,
                                           'building_type:' + second_type)
                first = vm.add(first_type, 40)
                same_province = vm.add(second_type, 30, location='second')
                other_province = vm.add(second_type, 20, location='third', province='other')
                vm.failures.add(first_type)
                self.assertEqual(vm.drain(), [first, other_province])
                self.assertEqual(vm.field('status', first), 5)
                self.assertEqual(vm.field('status', same_province), 1)
                self.assertEqual(vm.field('status', other_province), 6)
                self.assertEqual(vm.lists[vm.ROOT]['eu5ab_batch_granaries'], ['other'])
                self.assertEqual(vm.drain(), [same_province])
                self.assertEqual(vm.field('status', same_province), 6)
                self.assertCountEqual(vm.lists[vm.ROOT]['eu5ab_batch_granaries'],
                                      ['province', 'other'])
                blocked = vm.add(first_type, 50, location='fourth')
                self.assertEqual(vm.drain(), [])
                self.assertEqual(vm.field('status', blocked), 7)

    def test_same_type_expansions_have_distinct_ids_and_baselines(self):
        vm = BatchVM()
        first = vm.add('a', 10, slots=3, build_kind=4)
        vm.drain()
        second = vm.lists[vm.ROOT]['eu5ab_batch_pool'][-1]
        self.assertNotEqual(first, second)
        self.assertEqual(vm.field('status', first), 6)
        vm.drain()
        self.assertEqual([r[0] for r in vm.commands], [first, second])
        self.assertEqual(vm.field('queue_before', first), 0)
        self.assertEqual(vm.field('queue_before', second), 1)
        self.assertEqual(vm.vars['location']['eu5ab_batch_slots'], 1)

    def test_stale_cost_receipts_and_resume_cannot_repeat_commands(self):
        for stale in ('current', 'month', 'year', 'owner', 'phase', 'cancel'):
            with self.subTest(stale=stale):
                vm = BatchVM()
                project = vm.add('a', 10)
                vm.scopes.update(eu5ab_batch_id=project, eu5ab_engine_cost=99,
                                 eu5ab_candidate_building='a')
                if stale in ('month', 'year'):
                    vm.vars[vm.ROOT]['eu5ab_scan_' + stale] += 1
                elif stale == 'owner': vm.owners['location'] = 'foreign'
                elif stale == 'phase': vm.vars[vm.ROOT]['eu5ab_q_phase'] += 1
                elif stale == 'cancel': vm.run('eu5ab_batch_resume', vm.ROOT)
                before = deepcopy((vm.vars, vm.variable_maps, vm.commands))
                vm.run('eu5ab_gui_batch_capture_cost')
                self.assertEqual((vm.vars, vm.variable_maps, vm.commands), before)

    def test_generated_screening_and_direct_native_debit_contract(self):
        f = generated_fixture()
        syntax_parse(f.effects)
        syntax_parse(f.values)
        syntax_parse(f.scripted_guis)
        effect = _blocks_for_token(f.effects, '\neu5ab_batch_issue = ')[0]
        self.assertLess(effect.index('eu5ab_batch_gold_before'), effect.index('construct_building'))
        self.assertLess(effect.index('construct_building'), effect.index('eu5ab_batch_debit'))
        for forbidden in ('add_gold', 'eu5ab_has_local_workforce', 'eu5ab_refresh_native_recipes'):
            self.assertNotIn(forbidden, effect)
        self.assertNotIn('eu5ab_gui_batch_capture_cost', f.engine_queue_gui)
        self.assertNotIn("GetList('eu5ab_batch_cost_requests')", f.engine_queue_gui)
        dispatch = _blocks_for_token(f.effects, '\neu5ab_dispatch_construction_batch = ')[0]
        self.assertNotIn('eu5ab_batch_publish_costs', dispatch)
        self.assertNotIn('eu5ab_batch_cost_ready', dispatch)

    def test_phase_pool_uses_native_cached_rank_then_starts_without_gui_roundtrip(self):
        vm = BatchVM()
        vm.vars[vm.ROOT].update(eu5ab_monthly_build_quota=2, eu5ab_global_candidates_per_location=2)
        vm.lists[vm.ROOT]['eu5ab_batch_pool'] = []
        for kind, rank in (('estimate_winner', 1), ('native_winner', 30), ('runner_up', 20)):
            vm.add(kind, rank)
        vm.lists[vm.ROOT]['eu5ab_batch_pool'] = []
        types = ['estimate_winner', 'native_winner', 'runner_up']
        vm.lists['location']['eu5ab_q_phase_5_types'] = types[:]
        vm.lists['location']['eu5ab_batch_screened_types'] = types[:]
        vm.lists['location']['eu5ab_batch_passed_types'] = types[:]
        vm.run('eu5ab_dispatch_construction_batch', vm.ROOT)
        self.assertEqual([r[2] for r in vm.commands], ['native_winner', 'runner_up'])
        self.assertFalse(vm.lists[vm.ROOT].get('eu5ab_batch_cost_requests'))
        self.assertNotIn('eu5ab_batch_waiting', vm.vars[vm.ROOT])

    def test_dispatch_drains_more_than_seventeen_expansions_without_another_tick(self):
        vm = BatchVM()
        vm.vars[vm.ROOT].update(eu5ab_monthly_build_quota=30, eu5ab_batch_phase=5)
        vm.add('a', 10, cost='10', slots=30, build_kind=4)
        vm.debits['a'] = Decimal(10)
        vm.run('eu5ab_dispatch_construction_batch', vm.ROOT)
        self.assertEqual(len(vm.commands), 30)
        self.assertEqual(len({row[0] for row in vm.commands}), 30)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_global_budget_spent'], 300)
        self.assertEqual(vm.vars['location']['eu5ab_batch_slots'], 0)
        self.assertNotIn('eu5ab_batch_waiting', vm.vars[vm.ROOT])

    def test_shared_output_and_input_reservations_return_on_failure(self):
        vm = BatchVM()
        project = vm.add('a', 10)
        quotes = vm.variable_maps['location']
        quotes['eu5ab_quote_net_output_wheat'] = {'a': 10}
        quotes['eu5ab_quote_net_input_wheat'] = {'a': 20}
        ledger = vm.variable_maps[vm.ROOT]
        ledger['eu5ab_batch_eu5ab_market_effective_demand_wheat'] = {'market': 100}
        ledger['eu5ab_batch_supply_wheat'] = {'market': 100}
        ledger['eu5ab_batch_output_wheat'] = {'market': 0, 'other_market': 7}
        f = generated_fixture()
        names = ['eu5ab_market_effective_demand_wheat_snapshot', 'eu5ab_market_pending_limit_wheat_snapshot',
                 'eu5ab_market_pending_wheat_snapshot', 'eu5ab_market_pending_wheat',
                 'eu5ab_market_pending_limit_wheat', 'eu5ab_market_pending_factor_wheat']
        vm.capacity_values.update({k: v for k, _, v in parse('\n'.join(
            _blocks_for_token(f.values, '\n' + n + ' = ')[0] for n in names))})
        vm.native['eu5ab_market_pending_known_wheat'] = True
        vm.run('eu5ab_batch_approve', vm.ROOT)
        self.assertEqual(ledger['eu5ab_batch_output_wheat'], {'market': 10, 'other_market': 7})
        self.assertEqual(ledger['eu5ab_batch_input_delta_wheat']['market'], 20)
        vm.run('eu5ab_batch_restore_quote', 'location')
        stack = [vm.ROOT, 'a']
        self.assertEqual(vm.value('eu5ab_market_pending_limit_wheat', stack), 32)
        self.assertAlmostEqual(float(vm.value('eu5ab_market_pending_factor_wheat', stack)), 1 - (10 / 32) ** 2)
        vm.failures.add('a')
        vm.run('eu5ab_batch_issue', vm.ROOT)
        self.assertEqual(vm.field('status', project), 5)
        self.assertEqual(ledger['eu5ab_batch_output_wheat'], {'market': 0, 'other_market': 7})
        self.assertEqual(ledger['eu5ab_batch_input_delta_wheat']['market'], 0)

    def test_market_pending_includes_rgo_only_for_raw_goods(self):
        vm = BatchVM()
        vm.add('a', 10)
        vm.vars['location']['eu5ab_pending_approval_market'] = 'market'
        names = ['eu5ab_market_pending_tools_snapshot', 'eu5ab_market_pending_wheat_snapshot']
        vm.capacity_values.update({k: v for k, _, v in parse('\n'.join(
            _blocks_for_token(generated_fixture().values, '\n' + name + ' = ')[0] for name in names))})
        ledger = vm.variable_maps[vm.ROOT]
        for good in ('tools', 'wheat'):
            ledger['eu5ab_batch_output_' + good] = {'market': 3}
            ledger['eu5ab_rgo_pending_output_' + good] = {'market': 4}
        self.assertEqual(vm.value(names[0], [vm.ROOT, 'a']), 3)
        self.assertEqual(vm.value(names[1], [vm.ROOT, 'a']), 7)

    def test_saved_cost_wait_is_retired_and_owned_candidates_start_immediately(self):
        vm = BatchVM()
        first, second = vm.add('a', 20), vm.add('b', 10, location='second')
        vm.vars[vm.ROOT].update(eu5ab_batch_phase=5, eu5ab_batch_waiting=1,
                               eu5ab_batch_cost_day=1)
        vm.lists[vm.ROOT]['eu5ab_batch_cost_requests'] = [97, 98]
        vm.variable_maps[vm.ROOT]['eu5ab_batch_cost_project'] = {97: first, 98: second}
        vm.owners['second'] = 'foreign'
        vm.run('eu5ab_dispatch_construction_batch', vm.ROOT)
        self.assertEqual(vm.field('status', second), 7)
        self.assertFalse(vm.lists[vm.ROOT]['eu5ab_batch_cost_requests'])
        self.assertEqual([row[0] for row in vm.commands], [first])
        self.assertNotIn('eu5ab_batch_waiting', vm.vars[vm.ROOT])

    def test_cleanup_releases_unissued_holds_and_preserves_real_start_once(self):
        vm = BatchVM()
        started = vm.add('a', 20)
        vm.drain()
        held = vm.add('b', 10)
        vm.run('eu5ab_batch_approve', vm.ROOT)
        self.assertEqual(vm.field('status', held), 2)
        expenditure, cash = vm.vars[vm.ROOT]['eu5ab_global_budget_spent'], vm.cash
        count = vm.variable_maps['location']['eu5ab_active_building_counts']['a']
        vm.run('eu5ab_batch_close', vm.ROOT)
        vm.run('eu5ab_batch_issue', vm.ROOT)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_global_budget_spent'], expenditure)
        self.assertEqual(vm.cash, cash)
        self.assertEqual(vm.variable_maps['location']['eu5ab_active_building_counts']['a'], count)
        self.assertEqual([r[0] for r in vm.commands], [started])
        self.assertNotIn('eu5ab_batch_reserved', vm.vars[vm.ROOT])

    def test_missing_market_finishes_screen_without_reading_economy_or_approving(self):
        vm = BatchVM()
        vm.add('a', 10)
        vm.vars[vm.ROOT].update(eu5ab_batch_ledger_month=7, eu5ab_batch_ledger_year=1436)
        vm.vars['location'].update(eu5ab_batch_failure_month=7, eu5ab_batch_failure_year=1436,
                                   eu5ab_batch_failure_country=vm.ROOT)
        vm.markets['location'] = None
        vm.vars['location'].update(eu5ab_quote_production_type='a',
                                   eu5ab_quote_production_reference_known=True)
        before = deepcopy(vm.variable_maps)
        vm.run('eu5ab_batch_screen_quote', 'location')
        self.assertEqual(vm.variable_maps, before)
        self.assertEqual(vm.lists['location']['eu5ab_batch_screened_types'], ['a'])
        self.assertFalse(vm.lists['location'].get('eu5ab_batch_passed_types'))
        self.assertEqual(vm.commands, [])
        self.assertFalse(any(k.startswith('eu5ab_quote_production_') for k in vm.vars['location']))

    def test_quote_prepares_monthly_market_prices_before_filter_snapshot(self):
        block = _blocks_for_token(
            generated_fixture().effects, '\neu5ab_batch_screen_quote = '
        )[0]
        prepared = block.index('eu5ab_prepare_candidate_market_prices = yes')
        filtered = block.index('eu5ab_prepare_candidate_filter_prices = yes')
        self.assertLess(prepared, filtered)


if __name__ == '__main__': unittest.main()
