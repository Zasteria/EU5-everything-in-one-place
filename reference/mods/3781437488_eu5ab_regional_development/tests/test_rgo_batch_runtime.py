"""Generated RGO batches: native calls are fixtures, control flow is real script."""
from copy import deepcopy
from decimal import Decimal as D
import unittest

from tests.test_construction_batch_runtime import BatchVM
from tests._generated import generated_fixture, _blocks_for_token
from tests._governor_script_vm import parse
from src.eu5autobuild import rgo_pending, rgo_queue

P = 'eu5ab_batch_rgo_'


class RgoBatchVM(BatchVM):
    def __init__(self):
        super().__init__()
        self.lists[self.ROOT].clear()
        self.scopes['eu5ab_engine_country'] = self.ROOT
        self.rgo_queues = {}
        self.rgo_reads = []
        self.cash = D(10000)
        self.vars[self.ROOT]['eu5ab_monthly_build_quota'] = 1000
        self.stubs['eu5ab_report_rgo_confirmed'] = lambda: None
        self.definitions.update({k: v for k, _, v in parse(rgo_pending.render_effects() + rgo_queue.render_effects())})
        self.capacity_triggers.update({k: v for k, _, v in parse(rgo_pending.render_triggers() + rgo_queue.render_triggers())})
        self.native['eu5ab_rgo_staffed_levels'] = 4
        self.native['eu5ab_rgo_jobs_per_expansion'] = 1
        name = 'eu5ab_recover_pending_rgo_screens'
        self.definitions[name] = parse(_blocks_for_token(generated_fixture().effects, '\n' + name + ' = ')[0])[0][2]

    def value(self, x, stack):
        if x == 'num_civil_constructions':
            return self.rgo_queues.get(stack[-1], 0) + super().value(x, stack)
        if x in ('rgo_level', 'max_rgo_workers', 'rgo_workers'):
            return 4
        if x == 'eu5ab_rgos_under_construction':
            return self.rgo_queues.get(stack[-1], 0)
        if isinstance(x, str):
            if x == 'raw_material':
                return self.vars[stack[-1]][P + 'snapshot_good']
            for name in ('num_civil_constructions', 'rgo_level'):
                if x.endswith('.' + name):
                    return self.value(name, stack + [self.target(x[:-(len(name) + 1)], stack)])
        return super().value(x, stack)

    def execute(self, entries, stack):
        i = 0
        while i < len(entries):
            k, _, _ = entries[i]
            end = i + 1
            if k == 'if':
                while end < len(entries) and entries[end][0] in ('else_if', 'else'):
                    end += 1
            if k == 'construct_rgo_upgrade':
                location = stack[-1]
                self.commands.append((self.scopes['eu5ab_batch_id'], location, 'rgo', self.cash))
                if location not in self.failures:
                    self.cash -= self.debits.get(location, D(10))
                    self.rgo_queues[location] = self.rgo_queues.get(location, 0) + 1
            else:
                if k == 'eu5ab_batch_rgo_refresh_group':
                    self.rgo_reads.append(self.scopes['eu5ab_batch_rgo_group'])
                super().execute(entries[i:end], stack)
            i = end

    def candidate(self, location, *, good='iron', market='market', base=100,
                  cost=10, output=1, demand=100, supply=0, labor=1, price=1, emergency=0):
        self.owners[location] = self.ROOT
        self.markets[location] = market
        self.vars.setdefault(location, {})
        self.lists.setdefault(location, {})
        self.run('eu5ab_batch_slots_ensure', location)
        self.vars[location].update({P + 'snapshot_' + k: v for k, v in dict(
            cost=D(cost), base=D(base), price=D(price), labor=D(labor), output=D(output),
            emergency=emergency, demand=D(demand), supply=D(supply), ready=1,
            owner=self.ROOT, market=market, good='goods:' + good, month=7, year=1436).items()})
        if not emergency:
            self.vars[location].pop(P + 'snapshot_emergency', None)
        self.lists[self.ROOT].setdefault('eu5ab_q_phase_5_rgo_locations', []).append(location)
        return location

    def prepare(self):
        self.run('eu5ab_batch_rgo_prepare', self.ROOT)

    def field(self, field, ident):
        return self.variable_maps[self.ROOT][P + field][ident]


class RgoBatchTests(unittest.TestCase):
    def test_legacy_boolean_emergency_becomes_numeric_without_arithmetic(self):
        vm = RgoBatchVM()
        vm.candidate('urgent', good='wheat', emergency=True)
        vm.candidate('ordinary')
        value = vm.value

        def strict_value(word, stack):
            if word == 'var:' + P + 'snapshot_emergency':
                self.fail('A saved boolean must not enter numeric arithmetic')
            return value(word, stack)

        vm.value = strict_value
        vm.prepare()
        self.assertEqual(vm.field('emergency', 1), 1)
        self.assertEqual(vm.field('emergency', 2), 0)
        self.assertEqual(vm.field('group_emergency', 1), 1)

    def test_pending_screen_recovers_before_batch_but_known_rejection_stays_closed(self):
        for legacy, recovered, allowed in ((False, True, True), (True, True, True),
                                           (False, False, True), (False, True, False)):
            with self.subTest(legacy=legacy, recovered=recovered, allowed=allowed):
                vm = RgoBatchVM()
                vm.candidate('pending')
                native = {'cost': 'eu5ab_rgo_expansion_cost', 'base': 'eu5ab_rgo_base_score',
                          'price': 'eu5ab_rgo_price_factor', 'labor': 'eu5ab_rgo_current_labor_factor',
                          'output': 'eu5ab_rgo_full_level_output', 'demand': 'eu5ab_rgo_market_demand',
                          'supply': 'eu5ab_rgo_market_supply'}
                vm.native.update({name: vm.vars['pending'][P + 'snapshot_' + field] for field, name in native.items()})
                name = 'eu5ab_rgo_expansion_allowed'
                body = parse(_blocks_for_token(generated_fixture().triggers, '\n' + name + ' = ')[0])[0][2]
                vm.capacity_triggers[name] = body
                vm.capacity_triggers.pop('eu5ab_rgo_pending_data_available')
                vm.native.update({k: True for k, _, _ in body if k != 'eu5ab_rgo_pending_allowed'})
                vm.native.update(eu5ab_rgo_food_emergency_enabled=False,
                                 eu5ab_rgo_market_pending_quantity=0,
                                 eu5ab_rgo_pending_data_available=False, eu5ab_rgo_pending_below_limit=True)
                vm.run('eu5ab_batch_rgo_screen', 'pending')
                self.assertNotIn(P + 'snapshot_ready', vm.vars['pending'])
                self.assertIn(P + 'snapshot_pending', vm.vars['pending'])
                if legacy:
                    vm.vars['pending'].pop(P + 'snapshot_evaluated')
                    vm.vars['pending'].pop(P + 'snapshot_pending')
                vm.native.update(eu5ab_rgo_pending_data_available=recovered, eu5ab_rgo_workforce_allowed=allowed)
                vm.run('eu5ab_recover_pending_rgo_screens', vm.ROOT)
                self.assertEqual(P + 'snapshot_ready' in vm.vars['pending'], recovered and allowed)
                if recovered and not allowed:
                    # A known rejection is not reconsidered merely because a
                    # live condition changes after the screening window.
                    vm.native['eu5ab_rgo_workforce_allowed'] = True
                    vm.run('eu5ab_recover_pending_rgo_screens', vm.ROOT)
                    self.assertNotIn(P + 'snapshot_ready', vm.vars['pending'])
                vm.prepare()
                self.assertEqual(len(vm.lists[vm.ROOT].get(P + 'records', [])), int(recovered and allowed))

    def test_screen_quote_request_and_cleanup_preserve_rgo_only_slots(self):
        vm = RgoBatchVM()
        vm.candidate('rgo_only')
        native = {'cost': 'eu5ab_rgo_expansion_cost', 'base': 'eu5ab_rgo_base_score',
                  'price': 'eu5ab_rgo_price_factor', 'labor': 'eu5ab_rgo_current_labor_factor',
                  'output': 'eu5ab_rgo_full_level_output', 'demand': 'eu5ab_rgo_market_demand',
                  'supply': 'eu5ab_rgo_market_supply'}
        vm.native.update({name: vm.vars['rgo_only'][P + 'snapshot_' + field] for field, name in native.items()})
        vm.native.update(eu5ab_rgo_expansion_allowed=True, eu5ab_rgo_food_emergency_enabled=False,
                         eu5ab_scan_month_current=True)
        vm.run('eu5ab_batch_rgo_screen', 'rgo_only')
        fixture = generated_fixture()
        for name in ('eu5ab_request_candidate_quotes', 'eu5ab_clear_candidate_quotes'):
            vm.stubs.pop(name, None)
            vm.definitions[name] = parse(_blocks_for_token(fixture.effects, '\n' + name + ' = ')[0])[0][2]
        vm.run('eu5ab_request_candidate_quotes', 'rgo_only')
        self.assertFalse(vm.lists['rgo_only'].get('eu5ab_quote_requests'))
        vm.run('eu5ab_clear_candidate_quotes', 'rgo_only')
        self.assertEqual(vm.vars['rgo_only']['eu5ab_batch_slots'], 3)
        vm.run('eu5ab_batch_rgo_run', vm.ROOT)
        self.assertEqual([c[1] for c in vm.commands], ['rgo_only'])
        self.assertEqual(vm.vars['rgo_only']['eu5ab_batch_slots_occupied'], 1)
        self.assertEqual(vm.vars['rgo_only']['eu5ab_batch_slots_held'], 0)

    def test_missing_ledger_is_repaired_and_mixed_holds_release_only_failed_slot(self):
        vm = RgoBatchVM()
        vm.candidate('mixed')
        vm.vars['mixed'].pop('eu5ab_batch_slots_ready')
        vm.slot_limits['mixed'] = 2
        vm.add('a', 200, cost='10', location='mixed')
        vm.failures.add('a')
        vm.run('eu5ab_batch_approve', vm.ROOT)
        vm.prepare()
        vm.run('eu5ab_batch_rgo_approve', vm.ROOT)
        self.assertEqual(vm.vars['mixed']['eu5ab_batch_slots_held'], 2)
        self.assertEqual(vm.vars['mixed']['eu5ab_batch_slots'], 0)
        vm.run('eu5ab_clear_candidate_quotes', 'mixed')
        vm.run('eu5ab_batch_issue', vm.ROOT)
        vm.run('eu5ab_batch_rgo_issue', vm.ROOT)
        self.assertEqual(vm.vars['mixed']['eu5ab_batch_slots'], 1)
        self.assertEqual(vm.vars['mixed']['eu5ab_batch_slots_held'], 0)
        vm.run('eu5ab_batch_close', vm.ROOT)
        vm.run('eu5ab_batch_slots_ensure', 'mixed')
        self.assertEqual(vm.vars['mixed']['eu5ab_batch_slots'], 1)

    def test_missing_ledger_before_rgo_approval_and_reload_reconcile_native_queue(self):
        vm = RgoBatchVM()
        vm.candidate('a')
        vm.prepare()
        for field in ('ready', 'owner', 'month', 'year'):
            vm.vars['a'].pop('eu5ab_batch_slots_' + field, None)
        vm.vars['a'].pop('eu5ab_batch_slots')
        vm.run('eu5ab_batch_rgo_approve', vm.ROOT)
        self.assertEqual(vm.vars['a']['eu5ab_batch_slots'], 2)
        vm.rgo_queues['a'] = 2  # Native/manual projects already present on load.
        vm.run('eu5ab_batch_resume', vm.ROOT)
        self.assertEqual(vm.vars['a']['eu5ab_batch_slots'], 1)
        self.assertFalse(vm.lists['a']['eu5ab_batch_slot_holds'])
        self.assertEqual(vm.commands, [])
        vm.vars[vm.ROOT]['eu5ab_scan_month'] = 8
        vm.rgo_queues['a'] = 1
        vm.run('eu5ab_batch_slots_ensure', 'a')
        self.assertEqual(vm.vars['a']['eu5ab_batch_slots'], 2)

    def test_permanent_rejections_leave_active_groups_despite_unrelated_hold(self):
        vm = RgoBatchVM()
        vm.candidate('first', base=200, good='copper')
        vm.candidate('full', base=100)
        vm.candidate('lost', base=90, good='wheat')
        vm.prepare()
        vm.vars['full']['eu5ab_batch_slots'] = 0
        vm.owners['lost'] = 'foreign'
        vm.run('eu5ab_batch_rgo_approve', vm.ROOT)
        self.assertEqual(vm.field('status', 2), 7)
        self.assertEqual(vm.field('status', 3), 7)
        self.assertFalse(vm.lists[vm.ROOT].get(P + 'deferred'))
        self.assertFalse(vm.lists[vm.ROOT].get(P + 'active_groups'))

    def test_dispatch_drains_rgos_and_continues_buildings_without_gui(self):
        vm = RgoBatchVM()
        for i in range(30):
            vm.candidate('r' + str(i), base=100 - i)
        vm.add('a', 100, cost='10', location='building')
        vm.lists[vm.ROOT]['eu5ab_q_phase_6_locations'] = ['building']
        vm.lists['building'].update(eu5ab_q_phase_6_types=['a'], eu5ab_batch_passed_types=['a'], eu5ab_batch_screened_types=['a'])
        vm.debits['a'] = D(10)
        vm.run('eu5ab_dispatch_construction_batch', vm.ROOT)
        self.assertEqual([c[1] for c in vm.commands], ['r' + str(i) for i in range(30)] + ['building'])
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_rgo_started_this_tick'], 30)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_global_budget_spent'], 310)
        self.assertNotIn('eu5ab_bridge_request', vm.vars[vm.ROOT])
        self.assertEqual(len({c[0] for c in vm.commands}), 31)

    def test_pending_changes_reorder_only_affected_group_and_retire_rows(self):
        vm = RgoBatchVM()
        vm.candidate('a', base=100, output=8, demand=10, supply=10)
        vm.candidate('b', base=99, output=8, demand=10, supply=10)
        vm.candidate('c', good='copper', base=50)
        vm.prepare()
        vm.rgo_reads.clear()
        vm.run('eu5ab_batch_rgo_approve', vm.ROOT)
        self.assertEqual([vm.field('location', i) for i in vm.lists[vm.ROOT][P + 'approved']], ['a', 'c'])
        self.assertNotIn(1, vm.lists[vm.ROOT][P + 'pool_iron'])
        self.assertEqual(vm.rgo_reads, [1, 3])
        vm.run('eu5ab_batch_rgo_issue', vm.ROOT)
        vm.run('eu5ab_batch_rgo_run', vm.ROOT)
        self.assertEqual([c[1] for c in vm.commands], ['a', 'c'])

    def test_native_failure_restores_pending_cash_and_slots_then_next_row_runs(self):
        vm = RgoBatchVM()
        vm.candidate('a', base=100, output=8, demand=10, supply=10)
        vm.candidate('b', base=99, output=8, demand=10, supply=10)
        vm.failures.add('a')
        vm.run('eu5ab_dispatch_construction_batch', vm.ROOT)
        self.assertEqual([c[1] for c in vm.commands], ['a', 'b'])
        self.assertEqual(vm.vars['a']['eu5ab_batch_slots'], 3)
        self.assertEqual(vm.vars['b']['eu5ab_batch_slots'], 2)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_global_budget_spent'], 10)
        self.assertEqual(vm.variable_maps[vm.ROOT][P + 'held_iron']['market'], 0)
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_rgo_pending_locations'], ['b'])
        self.assertNotIn('eu5ab_rgo_pending_levels', vm.vars['a'])

    def test_budget_last_success_may_overshoot_and_blocks_preapproved_tail(self):
        for estimate, debit, budget in ((100, 120, 50), (10, 120, 50)):
            with self.subTest(estimate=estimate):
                vm = RgoBatchVM()
                vm.vars[vm.ROOT].update(eu5ab_global_budget_limit=budget, eu5ab_global_budget_remaining=budget)
                vm.candidate('a', base=100, cost=estimate)
                vm.candidate('b', base=90, cost=estimate)
                vm.debits['a'] = D(debit)
                vm.run('eu5ab_dispatch_construction_batch', vm.ROOT)
                self.assertEqual([c[1] for c in vm.commands], ['a'])
                self.assertEqual(vm.vars[vm.ROOT]['eu5ab_global_budget_spent'], debit)
                self.assertEqual(vm.vars[vm.ROOT]['eu5ab_batch_reserved'], 0)

    def test_cash_skip_and_success_settlement_are_idempotent(self):
        vm = RgoBatchVM()
        vm.cash = D('70.00001')
        vm.candidate('a', base=100, cost=30)
        vm.candidate('b', base=90, cost=20)
        vm.debits['b'] = D(20)
        vm.prepare()
        vm.run('eu5ab_batch_rgo_approve', vm.ROOT)
        vm.run('eu5ab_batch_rgo_issue', vm.ROOT)
        self.assertEqual([c[1] for c in vm.commands], ['b'])
        self.assertEqual(vm.cash, D('50.00001'))
        before = deepcopy((vm.commands, vm.cash, vm.vars[vm.ROOT]['eu5ab_global_budget_spent']))
        vm.run('eu5ab_batch_rgo_issue', vm.ROOT)
        vm.run('eu5ab_batch_rgo_confirm', vm.ROOT)
        self.assertEqual((vm.commands, vm.cash, vm.vars[vm.ROOT]['eu5ab_global_budget_spent']), before)

    def test_month_cancel_owner_resource_and_old_gui_receipt_cannot_issue(self):
        for mode in ('month', 'cancel', 'owner', 'resource'):
            with self.subTest(mode=mode):
                vm = RgoBatchVM()
                vm.candidate('a')
                vm.prepare()
                vm.run('eu5ab_batch_rgo_approve', vm.ROOT)
                self.assertFalse(vm.lists[vm.ROOT].get('eu5ab_rgo_pending_locations'))
                if mode == 'month': vm.vars[vm.ROOT]['eu5ab_scan_month'] = 8
                elif mode == 'cancel': vm.vars[vm.ROOT].pop('eu5ab_q_active')
                elif mode == 'owner': vm.owners['a'] = 'foreign'
                else: vm.vars['a'][P + 'snapshot_good'] = 'goods:silver'
                vm.run('eu5ab_gui_bridge_rgo', 'a')
                vm.run('eu5ab_batch_rgo_issue', vm.ROOT)
                self.assertEqual(vm.commands, [])
                self.assertEqual(vm.vars[vm.ROOT]['eu5ab_batch_reserved'], 0)
                self.assertFalse(vm.lists[vm.ROOT].get('eu5ab_rgo_pending_locations'))

    def test_fixed_formula_and_stable_tie_follow_existing_order(self):
        vm = RgoBatchVM()
        vm.candidate('a', base=50, price='.8', labor='.4')
        vm.candidate('b', good='copper', base=16)
        vm.candidate('c', base=16)
        vm.prepare()
        self.assertEqual(vm.field('score', 1), D(16))
        vm.run('eu5ab_batch_rgo_approve', vm.ROOT)
        self.assertEqual([vm.field('location', i) for i in vm.lists[vm.ROOT][P + 'approved']], ['a', 'b', 'c'])

    def test_ordinary_output_and_future_inputs_feed_rgo_and_rgo_feeds_buildings(self):
        vm = RgoBatchVM()
        vm.candidate('a', output=8, demand=10, supply=10)
        vm.vars[vm.ROOT].update(eu5ab_batch_ledger_month=7, eu5ab_batch_ledger_year=1436)
        vm.lists[vm.ROOT]['eu5ab_batch_markets'] = ['market']
        maps = vm.variable_maps.setdefault(vm.ROOT, {})
        for field, amount in (('eu5ab_market_effective_demand', 10), ('supply', 10), ('output', 8)):
            maps['eu5ab_batch_' + field + '_iron'] = {'market': D(amount)}
        vm.prepare()
        vm.run('eu5ab_batch_rgo_select', vm.ROOT)
        self.assertNotIn(P + 'winner', vm.vars[vm.ROOT])
        maps['eu5ab_batch_input_delta_iron'] = {'market': D(100)}
        vm.scopes['eu5ab_batch_rgo_group'] = 1
        vm.run('eu5ab_batch_rgo_refresh_group', vm.ROOT)
        vm.run('eu5ab_batch_rgo_approve', vm.ROOT)
        vm.run('eu5ab_batch_rgo_issue', vm.ROOT)
        self.assertEqual([c[1] for c in vm.commands], ['a'])
        self.assertEqual(maps['eu5ab_rgo_pending_output_iron']['market'], 8)
        # Execute the ordinary candidate's actual shared-ledger reader.
        f = generated_fixture()
        vm.capacity_values.update({k: v for k, _, v in parse(
            _blocks_for_token(f.values, '\neu5ab_market_pending_iron_snapshot = ')[0])})
        vm.vars['a']['eu5ab_pending_approval_market'] = 'market'
        self.assertEqual(vm.value('eu5ab_market_pending_iron_snapshot', ['a']), 16)

    def test_reload_releases_holds_and_preserves_failed_attempts_after_legacy_clear(self):
        vm = RgoBatchVM()
        vm.candidate('a')
        vm.candidate('b', base=90)
        vm.failures.add('a')
        vm.prepare()
        vm.run('eu5ab_batch_rgo_approve', vm.ROOT)
        vm.run('eu5ab_batch_rgo_issue', vm.ROOT)
        paid = vm.vars[vm.ROOT]['eu5ab_global_budget_spent']
        vm.run('eu5ab_batch_rgo_close', vm.ROOT)
        for location in ('a', 'b'):
            vm.vars[location].pop('eu5ab_q_rgo_attempted')
        vm.prepare()
        vm.run('eu5ab_batch_rgo_approve', vm.ROOT)
        vm.run('eu5ab_batch_rgo_issue', vm.ROOT)
        self.assertEqual([c[1] for c in vm.commands], ['a', 'b'])
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_global_budget_spent'], paid)


if __name__ == '__main__':
    unittest.main()
