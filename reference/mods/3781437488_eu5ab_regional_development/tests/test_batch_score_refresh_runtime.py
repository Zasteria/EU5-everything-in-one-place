"""Real generated score refreshes, with native quotes/construction as inputs."""
from collections import Counter
from copy import deepcopy
from decimal import Decimal, ROUND_DOWN
import unittest

from tests._generated import generated_fixture, _blocks_for_token
from tests._governor_script_vm import parse
from tests.test_construction_batch_runtime import BatchVM


class ScoreBatchVM(BatchVM):
    GOODS = ('tools', 'iron', 'wheat')
    KIND = 'building_type:iron_foundry'

    def __init__(self):
        super().__init__()
        self.refreshes = []
        self.approval_writes = Counter()
        self.index_visits = set()
        self.stubs.pop('eu5ab_batch_update_market_scores')
        self.stubs.pop('eu5ab_clear_recipe_score_snapshot')
        f = generated_fixture()

        def load(source, names, target):
            for name in names:
                target.update({k: v for k, _, v in parse(_blocks_for_token(source, '\n' + name + ' = ')[0])})

        load(f.effects, ('eu5ab_clear_recipe_score_snapshot', 'eu5ab_clear_candidate_quotes'), self.definitions)
        values = ['eu5ab_current_candidate_score', 'eu5ab_profit_candidate_rank_value',
                  'eu5ab_pending_profit_rank', 'eu5ab_pending_weight', 'eu5ab_pending_weighted']
        for name in ('eu5ab_price_adjusted_candidate_score', 'eu5ab_candidate_capacity_factor',
                     'eu5ab_candidate_pending_factor', 'eu5ab_candidate_pending_preliminary_factor',
                     'eu5ab_pending_adjusted_candidate_score'):
            values.append(name)
            if 'pending' in name:
                values.append(name + '_live')
        for good in self.GOODS:
            values += [f'eu5ab_candidate_net_output_{good}', f'eu5ab_market_pending_factor_{good}']
            for name in ('effective_demand', 'pending_limit', 'pending'):
                values += [f'eu5ab_market_{name}_{good}', f'eu5ab_market_{name}_{good}_snapshot']
        load(f.values, values, self.capacity_values)
        load(f.triggers, ('eu5ab_candidate_pending_allowed', 'eu5ab_pending_identity_known',
             'eu5ab_candidate_has_direct_output', 'eu5ab_candidate_output_limits_allow',
             'eu5ab_candidate_produces_food', 'eu5ab_food_emergency_enabled',
             *(f'eu5ab_market_pending_known_{g}' for g in self.GOODS)), self.capacity_triggers)
        for name in values:
            self.native.pop(name, None)

    def normalize_arithmetic(self, value):
        if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
            return Decimal(str(value)).quantize(Decimal('0.00001'), rounding=ROUND_DOWN)
        return value

    def value(self, x, stack):
        if isinstance(x, str):
            if x.startswith('default_price(goods:'):
                return Decimal(1)
            # The parent identity harness bypasses this factor; execute it here.
            if x == 'eu5ab_pending_profit_rank':
                return self.value(self.capacity_values[x], stack)
            if x == 'variable_map(eu5ab_batch_status|scope:eu5ab_batch_refresh_id)':
                self.index_visits.add(self.scopes['eu5ab_batch_refresh_id'])
        return super().value(x, stack)

    def execute(self, entries, stack):
        if hasattr(self, 'refreshes'):
            if entries is self.definitions.get('eu5ab_batch_refresh_quote_pending'):
                self.refreshes.append((self.scopes['eu5ab_batch_refresh_location'],
                                       self.scopes['eu5ab_batch_refresh_type']))
            for name, _, value in entries:
                if name == 'add_to_variable_map':
                    fields = {k: v for k, _, v in value}
                    if fields['name'].startswith('eu5ab_pending_approval_'):
                        self.approval_writes[fields['name']] += 1
        return super().execute(entries, stack)

    def test(self, key, operator, value, stack):
        if key == 'switch':
            fields = {k: v for k, _, v in value}
            return self.condition(fields.get(self.value(fields['trigger'], stack),
                                             fields.get('fallback', [])), stack)
        return super().test(key, operator, value, stack)

    def quote(self, location, score=100, *, outputs=None, inputs=None, market='market', kind=None, build_kind=3):
        kind = kind or self.KIND
        fields = dict(rank_base=score, eu5ab_price_adjusted_candidate_score=score,
                      eu5ab_candidate_capacity_factor=1, capacity_factor=1, identity_known=1)
        for good, quantity in (outputs if outputs is not None else {'tools': 8}).items():
            fields['net_output_' + good] = quantity
        for good, quantity in (inputs or {}).items():
            fields['net_input_' + good] = quantity
        maps = self.variable_maps.setdefault(location, {})
        for field, value in fields.items():
            maps.setdefault('eu5ab_quote_' + field, {})[kind] = value
        project = self.add(kind, score, cost='10', location=location, market=market, build_kind=build_kind)
        ledger = self.variable_maps[self.ROOT]
        for good in self.GOODS:
            for prefix, value in (('eu5ab_market_effective_demand', 100), ('supply', 100),
                                  ('output', 0), ('input_delta', 0), ('pending_known', 1)):
                ledger.setdefault(f'eu5ab_batch_{prefix}_{good}', {}).setdefault(market, value)
        return project

    def select(self, project):
        self.scopes['eu5ab_batch_id'] = project
        self.run('eu5ab_batch_select_context', self.ROOT)

    def refresh(self, project):
        self.select(project)
        self.scopes['eu5ab_batch_refresh_location'] = self.scopes['eu5ab_candidate_location']
        self.scopes['eu5ab_batch_refresh_type'] = self.scopes['eu5ab_candidate_building']
        self.run('eu5ab_batch_refresh_quote_pending', self.scopes['eu5ab_candidate_location'])


class BatchScoreRefreshTests(unittest.TestCase):
    def test_light_refresh_matches_full_restore_without_touching_start_geometry(self):
        vm = ScoreBatchVM()
        project = vm.quote('location')
        light = deepcopy(vm.definitions['eu5ab_batch_refresh_quote_pending'])
        # Retain the previous full-restore route as a differential control.
        old = _blocks_for_token(generated_fixture().effects, '\neu5ab_batch_refresh_quote_pending = ')[0]
        full = parse(old.replace('eu5ab_batch_restore_score_context = yes', 'eu5ab_batch_restore_quote = yes'))[0][2]
        for mode in (0, 2):
            for base, pending, known in ((100, 8, True), (-100, 8, True), (0, 0, True),
                                          (100, 20, True), (100, 8, False)):
                with self.subTest(mode=mode, base=base, pending=pending, known=known):
                    case = deepcopy(vm)
                    case.vars[case.ROOT]['eu5ab_batch_ranking_mode'] = mode
                    maps = case.variable_maps['location']
                    for field in ('rank_base', 'eu5ab_price_adjusted_candidate_score'):
                        maps['eu5ab_quote_' + field][case.KIND] = base
                    case.variable_maps[case.ROOT]['eu5ab_batch_output_tools']['market'] = pending
                    if not known:
                        case.variable_maps[case.ROOT]['eu5ab_batch_pending_known_tools'].pop('market')
                    case.vars['location'].update(eu5ab_pf_reference_building='saved_donor',
                                                  eu5ab_pending_predecessor='saved_predecessor')
                    maps['eu5ab_pending_approval_old_output'] = {'goods:tools': 123}
                    control = deepcopy(case)
                    case.definitions['eu5ab_batch_refresh_quote_pending'] = light
                    control.definitions['eu5ab_batch_refresh_quote_pending'] = full
                    case.refresh(project)
                    control.refresh(project)
                    for field in ('score', 'pending_open', 'ledger_generation'):
                        self.assertEqual(case.variable_maps['location']['eu5ab_quote_' + field],
                                         control.variable_maps['location']['eu5ab_quote_' + field])
                    self.assertFalse(case.approval_writes)
                    self.assertGreater(sum(control.approval_writes.values()), 0)
                    self.assertEqual(case.vars['location']['eu5ab_pf_reference_building'], 'saved_donor')
                    self.assertEqual(maps['eu5ab_pending_approval_old_output'], {'goods:tools': 123})
                    self.assertNotIn('eu5ab_batch_quote_restored', case.vars['location'])

    def test_index_limits_visits_to_market_goods_and_refreshes_each_candidate_once(self):
        vm = ScoreBatchVM()
        source = vm.quote('source', outputs={'tools': 8}, inputs={'iron': 2})
        affected = vm.quote('affected', outputs={'tools': 4, 'iron': 3})
        deferred = vm.quote('deferred', outputs={'iron': 2})
        vm.variable_maps[vm.ROOT]['eu5ab_batch_status'][deferred] = 8
        other_market = vm.quote('elsewhere', market='other_market')
        unrelated = vm.quote('unrelated', outputs={'wheat': 5})
        foreign = vm.quote('foreign')
        retired = vm.quote('retired')
        vm.variable_maps[vm.ROOT]['eu5ab_batch_status'][retired] = 7
        vm.owners['foreign'] = 'other_country'
        foreign_before = deepcopy((vm.vars['foreign'], vm.variable_maps['foreign']))
        vm.select(source)
        vm.run('eu5ab_batch_reserve', vm.ROOT)
        self.assertEqual(Counter(loc for loc, _ in vm.refreshes), Counter(affected=1, deferred=1))
        self.assertNotIn(other_market, vm.index_visits)
        self.assertNotIn(unrelated, vm.index_visits)
        self.assertIn(affected, vm.index_visits)
        self.assertIn(foreign, vm.index_visits)
        self.assertEqual((vm.vars['foreign'], vm.variable_maps['foreign']), foreign_before)
        self.assertFalse(vm.lists[vm.ROOT]['eu5ab_batch_score_dirty'])
        self.assertNotIn('eu5ab_batch_score_seen', vm.variable_maps[vm.ROOT])
        self.assertEqual(vm.scopes['eu5ab_batch_id'], source)
        self.assertEqual(vm.scopes['eu5ab_candidate_location'], 'source')

    def test_real_reservations_reorder_approvals_and_preserve_pool_ties(self):
        vm = ScoreBatchVM()
        first = vm.quote('first', 100)
        same_market = vm.quote('same_market', 90)
        other_market = vm.quote('other_market', 80, market='other_market')
        tied_market = vm.quote('tied_market', 80, market='tied_market')
        vm.cash = Decimal(1000)
        vm.debits[vm.KIND] = Decimal(10)
        expected = [first, other_market, tied_market, same_market]
        self.assertEqual(vm.drain(), expected)
        self.assertEqual([r[0] for r in vm.commands], expected)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_global_budget_spent'], 40)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_constructions_started_this_tick'], 4)
        self.assertEqual(vm.cash, 960)
        for project in expected:
            self.assertEqual(vm.field('status', project), 6)

    def test_failed_start_releases_output_and_future_input_and_restores_rank(self):
        vm = ScoreBatchVM()
        first = vm.quote('first', outputs={'tools': 30}, inputs={'tools': 5})
        second = vm.quote('second', 90)
        vm.select(first)
        vm.run('eu5ab_batch_reserve', vm.ROOT)
        self.assertEqual(vm.variable_maps['second']['eu5ab_quote_pending_open'][vm.KIND], 0)
        vm.failures.add(vm.KIND)
        vm.run('eu5ab_batch_issue', vm.ROOT)
        self.assertEqual(vm.field('status', first), 5)
        self.assertEqual(vm.field('status', second), 1)
        self.assertEqual(vm.field('score', second), 90)
        self.assertEqual(vm.variable_maps['second']['eu5ab_quote_pending_open'][vm.KIND], 1)
        for prefix in ('output', 'input_delta'):
            self.assertEqual(vm.variable_maps[vm.ROOT][f'eu5ab_batch_{prefix}_tools']['market'], 0)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_global_budget_spent'], 0)
        self.assertEqual(vm.cash, Decimal('1000.12345'))

    def test_new_rows_and_changed_quotes_rebuild_or_extend_the_derived_index(self):
        vm = ScoreBatchVM()
        source = vm.quote('source', inputs={'iron': 2})
        vm.run('eu5ab_batch_ensure_score_index', vm.ROOT)
        added = vm.quote('added', outputs={'iron': 4}, build_kind=4)
        vm.select(source)
        vm.run('eu5ab_batch_reserve', vm.ROOT)
        self.assertIn(('added', vm.KIND), vm.refreshes)
        # Same-month replacement of a quote invalidates all derived links.
        vm.run('eu5ab_clear_candidate_quotes', 'added')
        self.assertNotIn('eu5ab_batch_score_index_ready', vm.vars[vm.ROOT])
        vm.variable_maps['added']['eu5ab_quote_net_output_wheat'] = {vm.KIND: 3}
        vm.run('eu5ab_batch_ensure_score_index', vm.ROOT)
        ledger = vm.variable_maps[vm.ROOT]
        self.assertNotIn(added, ledger.get('eu5ab_batch_score_next_iron', {}))
        self.assertEqual(ledger['eu5ab_batch_score_head_wheat']['market'], added)

    def test_phase_load_close_and_month_ledger_reset_clear_derived_state(self):
        for effect in ('eu5ab_batch_prepare_phase', 'eu5ab_batch_resume',
                       'eu5ab_batch_close', 'eu5ab_batch_reset_ledgers'):
            with self.subTest(effect=effect):
                vm = ScoreBatchVM()
                vm.quote('source')
                vm.run('eu5ab_batch_ensure_score_index', vm.ROOT)
                vm.lists[vm.ROOT]['eu5ab_q_phase_5_locations'] = []
                vm.run(effect, vm.ROOT)
                self.assertNotIn('eu5ab_batch_score_index_ready', vm.vars[vm.ROOT])
                self.assertFalse(any(k.startswith(('eu5ab_batch_score_head_', 'eu5ab_batch_score_next_'))
                                     for k in vm.variable_maps[vm.ROOT]))
                self.assertFalse(vm.commands)


if __name__ == '__main__':
    unittest.main()
