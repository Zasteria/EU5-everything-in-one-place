"""Compare worker memoization with live gates, including engine-dropped zero.

Native admission facts are injected in the collection VM; selected recipes and
fixed-point prices are executed in the price VM. No offline timings represent
game performance.
"""
from collections import Counter
import random
import unittest

from src.eu5autobuild.generator import _catalog_building_ids, _upstream_output_shortage_condition_lines
from src.eu5autobuild.worker_screening import ACTIVE, PREDICATES, PRICE_VALUES, mapping, prepare, render_effects
from tests._generated import _blocks_for_token, generated_fixture
from tests._game_data_fixtures import cached_game_data
from tests._governor_script_vm import parse
from tests.test_candidate_collection_runtime import CollectionVM, NORMAL, INPUT, CLEAR
from tests import test_candidate_collection_runtime as collection
from tests.test_engine import RULES
from tests.test_output_prices_runtime import PriceVM
from tests.test_pending_goods_runtime import PendingGoodsVM


class WorkerVM(CollectionVM):
    def __init__(self, definitions, rows, *, memo=True, policy=100):
        super().__init__(definitions, rows, policy=policy)
        if memo:
            for location in ('location', 'other'):
                self.vars[location][ACTIVE] = True
        self.vars[self.ROOT].update(eu5ab_candidate_priority_upgrade=3,
                                   eu5ab_candidate_priority_expand=2,
                                   eu5ab_candidate_priority_new=1)
        self.staged = []

    def test(self, k, op, v, stack):
        if k == 'always':
            return v == 'yes'
        if k in PREDICATES.values():
            return self.condition(self.definitions[k], stack) == (v == 'yes')
        live = k.removesuffix('_worker_live')
        fields = {'eu5ab_inputs_available': 'inputs',
                  'eu5ab_candidate_pending_data_ready': 'pending_ready',
                  'eu5ab_candidate_pending_preliminary_allowed': 'pending_allowed',
                  'eu5ab_output_price_data_valid': 'price_valid',
                  'eu5ab_candidate_production_cooldown_clear': 'cooldown'}
        if live in fields:
            self.queries[(live, stack[-1])] += 1
            row = self.rows[stack[-1]]
            result = row.get(fields[live], True)
            if live == 'eu5ab_candidate_pending_preliminary_allowed':
                result = self.test('eu5ab_candidate_production_cooldown_clear', '=', 'yes', stack) and self.test('eu5ab_candidate_pending_data_ready', '=', 'yes', stack) and result
            return result == (v == 'yes')
        if k == 'eu5ab_output_not_oversupplied':
            return (self.test('eu5ab_output_price_data_valid', '=', 'yes', stack)
                    and self.value('eu5ab_output_price_factor_live', stack) > 0) == (v == 'yes')
        if k == 'exists' and v == 'market':
            return self.rows[self.scopes['eu5ab_candidate_building']].get('market', True)
        if k == 'eu5ab_food_emergency_enabled':
            return False
        return super().test(k, op, v, stack)

    def value(self, word, stack):
        if isinstance(word, str) and word.startswith('scope:eu5ab_candidate_building.eu5ab_'):
            return self.value(word.split('.', 1)[1], stack + [self.scopes['eu5ab_candidate_building']])
        if isinstance(word, str) and word.endswith('_live_worker_live') and word.removesuffix('_live_worker_live') in PRICE_VALUES:
            name = word.removesuffix('_live_worker_live')
            self.queries[(name, stack[-1])] += 1
            row = self.rows[stack[-1]]
            if name == 'eu5ab_output_price_factor':
                if not self.test('eu5ab_output_price_data_valid', '=', 'yes', stack):
                    return 0
                weight = self.value('eu5ab_output_weight_live', stack)
                return self.value('eu5ab_output_low_weight_live', stack) / weight if weight else 1
            return 1 if name == 'eu5ab_output_weight' else float(row['output'])
        if isinstance(word, str) and word in (name + '_live' for name in PRICE_VALUES):
            return self.value(self.definitions[word], stack)
        return super().value(word, stack)

    def execute(self, entries, stack):
        # Avoid CollectionVM's injected-effect shortcut: execute real memoization.
        index = 0
        while index < len(entries):
            k, _, v = entries[index]
            end = index + 1
            if k == 'if':
                while end < len(entries) and entries[end][0] in ('else_if', 'else'):
                    end += 1
            if k.startswith('eu5ab_prepare_worker_screen_'):
                self.execute(self.definitions[k], stack)
            elif k == 'eu5ab_try_construct_saved_building_type':
                location = self.scopes['eu5ab_candidate_location']
                if not self.vars[location].get('eu5ab_action_taken'):
                    self.staged.append((location, stack[-1], self.vars[location]['eu5ab_stage_candidate_priority']))
            elif k == 'add_to_variable_map':
                data = {a: c for a, _, c in v}
                target, result = self.value(data['key'], stack), self.value(data['value'], stack)
                if result == 0:
                    self.maps[stack[-1]].setdefault(data['name'], {}).pop(target, None)
                else:
                    self.maps[stack[-1]].setdefault(data['name'], {})[target] = result
            else:
                super().execute(entries[index:end], stack)
            index = end


class WorkerPriceVM(PriceVM):
    def __init__(self):
        super().__init__()
        self.maps = {}
        self.reads = Counter()
        self.in_location = 0
        self.variables[ACTIVE] = True
        self.models = cached_game_data()[0]

    def key(self, expression):
        if expression in ('prev', 'scope:eu5ab_candidate_building'):
            return 'building_type:' + self.building
        return expression

    def value(self, expression):
        if isinstance(expression, str):
            word = expression.strip('"')
            if '.variable_map(' in word:
                word = word.split('.', 1)[1]
            if word.startswith('variable_map('):
                name, target = word[len('variable_map('):-1].split('|')
                return self.maps.get(name, {}).get(self.key(target), 0)
            if word.startswith('scope:eu5ab_candidate_building.'):
                return self.value(word.split('.', 1)[1])
            if word.startswith(('owner.eu5ab_manual_value_',
                                'scope:eu5ab_candidate_location.owner.eu5ab_manual_value_')):
                # Country settings share this VM's single variable context.
                return self.value(word.rsplit('.', 1)[1])
            if word.endswith('_worker_live'):
                self.reads[word] += 1
        return super().value(expression)

    def predicate(self, key, op, value):
        if key == 'has_variable_map':
            return bool(self.maps.get(value))
        if key == 'is_key_in_variable_map':
            data = {a: c for a, _, c in value}
            return self.key(data['target']) in self.maps.get(data['name'], {})
        if key == 'scope:eu5ab_candidate_building':
            return self.condition(value)
        if key == 'scope:eu5ab_candidate_location.owner':
            return self.condition(value)
        if key == 'owner':
            return self.condition(value)
        if key.endswith('_worker_live'):
            self.reads[key] += 1
        return super().predicate(key, op, value)

    def run(self, entries, result=0):
        # This VM represents one location and its building scope in one object.
        expanded = []
        for key, op, value in entries:
            if key in ('scope:eu5ab_candidate_location', 'scope:eu5ab_candidate_location.owner'):
                expanded.extend(value)
            else:
                expanded.append((key, op, value))
        return super().run(expanded, result)

    def execute(self, entries):
        matched = False
        for key, _, value in entries:
            if key in ('if', 'else_if', 'else'):
                if key == 'if':
                    matched = False
                if not matched and (key == 'else' or self.condition(value[0][2])):
                    self.execute(value if key == 'else' else value[1:])
                    matched = True
            elif key == 'add_to_variable_map':
                data = {a: c for a, _, c in value}
                result = self.value(data['value'])
                target = self.key(data['key'])
                if result == 0:
                    self.maps.setdefault(data['name'], {}).pop(target, None)
                else:
                    self.maps.setdefault(data['name'], {})[target] = result
            elif key == 'clear_variable_map':
                self.maps[value] = {}
            elif key == 'scope:eu5ab_candidate_building':
                self.execute(value)
            elif key in ('scope:eu5ab_candidate_location.owner', 'owner'):
                self.execute(value)
            else:
                super().execute([(key, '=', value)])


class UpstreamVM(WorkerPriceVM):
    def predicate(self, key, op, value):
        if key == 'eu5ab_native_recipes_current':
            return self.native_current == (value == 'yes')
        if key == 'has_variable_map':
            return bool(self.maps.get(value))
        if key == 'is_target_in_variable_list':
            data = {a: c for a, _, c in value}
            if data['name'] == 'eu5ab_native_recipe_types':
                return data['target'] == 'building_type:' + self.building and self.native_current
        if key.startswith('eu5ab_market_needs_'):
            # Pending ledger validity/allowance is an injected stable fact;
            # the supply, demand and high-price OR below still executes.
            return self.pending_known == (value == 'yes')
        if key.startswith('eu5ab_market_upstream_shortage_'):
            return self.condition(self.triggers[key]) == (value == 'yes')
        return super().predicate(key, op, value)


class WorkerScreeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = generated_fixture()
        names = (NORMAL, INPUT, CLEAR, 'eu5ab_prepare_candidate_workforce',
                 'eu5ab_prepare_worker_screen_upgrades',
                 'eu5ab_prepare_candidate_collection_gate',
                 *(f'eu5ab_stage_current_{prefix}{kind}_candidates' for prefix in ('', 'input_') for kind in ('upgrade', 'expansion', 'new')))
        cls.definitions = {name: parse(_blocks_for_token(fixture.effects, '\n' + name + ' = ')[0])[0][2] for name in names}
        cls.definitions.update({k: v for k, _, v in parse(render_effects())})
        cls.definitions.update({name: parse(_blocks_for_token(fixture.triggers, '\n' + name + ' = ')[0])[0][2]
                                for name in (*PREDICATES.values(), 'eu5ab_upstream_output_shortage_preliminary')})
        cls.definitions.update({name + '_live': parse(_blocks_for_token(fixture.values, '\n' + name + '_live = ')[0])[0][2]
                                for name in PRICE_VALUES})

    def run_pools(self, vm):
        vm.run(NORMAL)
        for kind in ('upgrade', 'expansion', 'new'):
            vm.run(f'eu5ab_stage_current_{kind}_candidates')
        vm.run(INPUT)
        for kind in ('upgrade', 'expansion', 'new'):
            vm.run(f'eu5ab_stage_current_input_{kind}_candidates')

    def test_cached_live_candidate_sets_reasons_priority_order_and_state(self):
        for policy in (1, 100):
            for seed in range(12):
                rng = random.Random(seed)
                rows = collection.CandidateCollectionRuntimeTests.rows(seed, 36)
                for row in rows.values():
                    row.update(pending_ready=rng.random() > .1, pending_allowed=rng.random() > .1,
                               price_valid=rng.random() > .1, cooldown=rng.random() > .1)
                    if policy == 1:
                        row['upstream_allowed'] = not row['allowed']
                cached = WorkerVM(self.definitions, rows, policy=policy)
                live = WorkerVM(self.definitions, rows, policy=policy, memo=False)
                for vm in (cached, live):
                    self.run_pools(vm)
                with self.subTest(policy=policy, seed=seed):
                    # Only compare published fields, excluding private memo data.
                    public = lambda vm: ({k: v for k, v in vm.result()[0].items()},
                                         {k: v for k, v in vm.result()[1].items() if not k.startswith('eu5ab_worker_screen_')})
                    self.assertEqual(public(cached), public(live))
                    self.assertEqual(cached.staged, live.staged)
                    for building in rows:
                        for name in (*PREDICATES.values(), *PRICE_VALUES):
                            self.assertLessEqual(cached.queries[(name, building)], 1, (name, building))
                    cached.run(CLEAR)
                    self.assertNotIn(ACTIVE, cached.vars['location'])
                    self.assertFalse(any(data for name, data in cached.maps['location'].items() if name.startswith('eu5ab_worker_screen_')))

    def test_unknown_failure_zero_and_uncalculated_are_distinct(self):
        rows = collection.CandidateCollectionRuntimeTests.rows(count=3)
        for row in rows.values():
            row.update(pending_ready=True, pending_allowed=True, price_valid=True, cooldown=True, inputs=True, output=False)
        rows['building_0']['pending_ready'] = False
        rows['building_1']['pending_allowed'] = False
        vm = WorkerVM(self.definitions, rows)
        vm.scopes.update(eu5ab_candidate_location='location', eu5ab_candidate_building='building_0')
        for b in ('building_0', 'building_1'):
            vm.scopes['eu5ab_candidate_building'] = b
            vm.execute(self.definitions[prepare('pending_allowed')], [b])
        self.assertEqual(vm.maps['location'][mapping('pending_allowed')], {'building_0': 3, 'building_1': 1})
        self.assertNotIn('building_2', vm.maps['location'][mapping('pending_allowed')])
        rows['building_2'].update(cooldown=False, pending_ready=False)
        vm.rows['building_2'].update(rows['building_2'])
        vm.scopes['eu5ab_candidate_building'] = 'building_2'
        vm.execute(self.definitions[prepare('pending_allowed')], ['building_2'])
        self.assertEqual(vm.maps['location'][mapping('pending_allowed')]['building_2'], 1)
        self.assertEqual(vm.queries[('eu5ab_candidate_production_cooldown_clear', 'building_2')], 1)
        self.assertEqual(vm.queries[('eu5ab_candidate_pending_data_ready', 'building_2')], 0)
        vm.scopes['eu5ab_candidate_building'] = 'building_2'
        vm.execute(self.definitions[prepare('prices')], ['building_2'])
        self.assertEqual(vm.maps['location'][mapping('price_valid')]['building_2'], 2)
        self.assertEqual(vm.maps['location'][mapping('output_price_factor_ready')]['building_2'], 1)
        self.assertNotIn('building_2', vm.maps['location'][mapping('output_price_factor')])
        before = vm.queries.copy()
        vm.execute(self.definitions[prepare('prices')], ['building_2'])
        self.assertEqual(vm.queries, before)

    def test_fresh_worker_other_location_standalone_and_action_taken(self):
        rows = collection.CandidateCollectionRuntimeTests.rows(count=1)
        rows['building_0'].update(inputs=True, output=True, price_valid=True,
                                  pending_allowed=True, pending_ready=True, cooldown=True)
        vm = WorkerVM(self.definitions, rows)
        vm.scopes.update(eu5ab_candidate_location='location', eu5ab_candidate_building='building_0')
        vm.execute(self.definitions[prepare('inputs')], ['building_0'])
        vm.rows['building_0']['inputs'] = False
        # The first worker still sees its synchronous snapshot.
        self.assertTrue(vm.test('eu5ab_inputs_available', '=', 'yes', ['building_0']))
        vm.scopes['eu5ab_candidate_location'] = 'other'
        vm.execute(self.definitions[prepare('inputs')], ['building_0'])
        self.assertFalse(vm.test('eu5ab_inputs_available', '=', 'yes', ['building_0']))
        self.assertEqual(vm.maps['location'][mapping('inputs')]['building_0'], 2)
        vm.scopes['eu5ab_candidate_location'] = 'location'
        vm.run(CLEAR)
        self.assertFalse(vm.test('eu5ab_inputs_available', '=', 'yes', ['building_0']))
        self.assertTrue(vm.maps['other'][mapping('inputs')])
        vm.vars['location'][ACTIVE] = True
        vm.execute(self.definitions[prepare('inputs')], ['building_0'])
        self.assertEqual(vm.maps['location'][mapping('inputs')]['building_0'], 1)
        vm.run(CLEAR)
        vm.vars['location'].update({ACTIVE: True, 'eu5ab_action_taken': True})
        vm.lists['location']['eu5ab_current_new_candidate_pool'] = ['building_0']
        before = vm.queries.copy()
        vm.run('eu5ab_stage_current_new_candidates')
        self.assertEqual(vm.queries, before)
        self.assertFalse(vm.staged)

    def test_real_pending_checks_new_expansion_upgrade_unknown_and_zero(self):
        fixture = generated_fixture()
        vm = PendingGoodsVM()
        names = (*PREDICATES.values(), *(name + '_worker_live' for name in PREDICATES.values()))
        vm.capacity_triggers.update({name: parse(_blocks_for_token(fixture.triggers, '\n' + name + ' = ')[0])[0][2] for name in names})
        vm.definitions.update({k: v for k, _, v in parse(render_effects())})
        target = 'building_type:iron_foundry'
        vm.scopes.update(eu5ab_candidate_location='location', eu5ab_candidate_building=target)
        for output, old_output, unknown, factor, identity in (
            (10, 0, False, 1, False),  # New construction, no known donor.
            (10, 0, False, .3, True),  # Expansion.
            (10, 7, False, .3, True),  # Upgrade net increment.
            (10, 10, True, 0, True),  # Valid zero output despite unknown goods.
            (10, 0, True, 1, True),   # Unknown pending data.
            (10, 0, False, 0, True),  # Known saturated output.
        ):
            vm.execute(vm.definitions['eu5ab_clear_worker_screening'], ['location'])
            vm.output, vm.old_output = {'tools': output}, {'tools': old_output}
            vm.unknown_goods = {'tools'} if unknown else set()
            vm.pending_factors = {'tools': factor}
            vm.identity_known = identity
            expected = vm.test('eu5ab_candidate_pending_preliminary_allowed', '=', 'yes', [target])
            vm.vars['location'][ACTIVE] = True
            vm.execute(vm.definitions[prepare('pending_allowed')], [target])
            self.assertEqual(vm.test('eu5ab_candidate_pending_preliminary_allowed', '=', 'yes', [target]), expected)
            before = list(vm.output_reads)
            vm.execute(vm.definitions[prepare('pending_allowed')], [target])
            vm.test('eu5ab_candidate_pending_preliminary_allowed', '=', 'yes', [target])
            vm.test('eu5ab_candidate_pending_data_ready', '=', 'yes', [target])
            self.assertEqual(vm.output_reads, before)
            vm.execute(vm.definitions['eu5ab_clear_worker_screening'], ['location'])
            self.assertEqual(vm.test('eu5ab_candidate_pending_preliminary_allowed', '=', 'yes', [target]), expected)

    def test_actual_fixed_point_prices_across_types_and_clear(self):
        vm = WorkerPriceVM()
        for building in ('mason', 'market_village', 'granary', 'windmill', 'fishing_village'):
            for price in (0, .8, .80001, .9, 1, 2):
                vm.building = building
                vm.execute(vm.effects['eu5ab_clear_worker_screening'])
                vm.execute(vm.effects['eu5ab_clear_scan_market_cache'])
                vm.prices = {g: price for m in vm.models.values() for s in m.slots for p in s for g in p.outputs}
                expected = vm.value('eu5ab_output_price_factor')
                valid = vm.condition(vm.triggers['eu5ab_output_price_data_valid'])
                vm.variables[ACTIVE] = True
                vm.reads.clear()
                vm.execute(vm.effects[prepare('prices')])
                self.assertEqual(vm.value('eu5ab_output_price_factor'), expected, (building, price))
                self.assertEqual(vm.condition(vm.triggers['eu5ab_output_price_data_valid']), valid)
                before = vm.reads.copy()
                for _ in range(3):
                    vm.execute(vm.effects[prepare('prices')])
                    self.assertEqual(vm.value('eu5ab_output_price_factor'), expected)
                self.assertEqual(vm.reads, before)
                self.assertEqual(vm.reads['eu5ab_output_price_data_valid_worker_live'], 1)
                for name in PRICE_VALUES:
                    self.assertLessEqual(vm.reads[name + '_live_worker_live'], 1)

    def test_market_good_price_snapshot_is_shared_until_monthly_clear(self):
        vm = WorkerPriceVM()
        vm.variables[ACTIVE] = True
        vm.prices['masonry'] = .9
        vm.execute(vm.effects['eu5ab_prepare_market_price_masonry'])
        self.assertEqual(float(vm.value('eu5ab_market_price_masonry')), .9)
        self.assertEqual(vm.price_queries, 1)

        # Quote screening has no worker-active flag but shares the same monthly
        # market x good snapshot.
        vm.variables.pop(ACTIVE)
        vm.prices['masonry'] = 2
        self.assertEqual(float(vm.value('eu5ab_market_price_masonry')), .9)
        self.assertEqual(vm.price_queries, 1)

        # A later worker or quote in the same scan does not refresh it.
        vm.execute(vm.effects['eu5ab_prepare_market_price_masonry'])
        self.assertEqual(float(vm.value('eu5ab_market_price_masonry')), .9)
        self.assertEqual(vm.price_queries, 1)

        vm.execute(vm.effects['eu5ab_clear_scan_market_cache'])
        vm.execute(vm.effects['eu5ab_prepare_market_price_masonry'])
        self.assertEqual(float(vm.value('eu5ab_market_price_masonry')), 2)
        self.assertEqual(vm.price_queries, 2)

    def test_missing_prices_outputless_emergency_and_skipped_numeric_stages(self):
        vm = WorkerPriceVM()
        for building, market, price, emergency in (
            ('mason', False, 1, False), ('granary', False, 0, False),
            ('mason', True, -1, False), ('mason', True, 0, False),
            ('fishing_village', True, .5, True), ('fishing_village', True, -1, True),
        ):
            vm.building, vm.market_exists, vm.exhaustion = building, market, emergency
            vm.execute(vm.effects['eu5ab_clear_worker_screening'])
            vm.execute(vm.effects['eu5ab_clear_scan_market_cache'])
            vm.prices = {g: price for m in vm.models.values() for s in m.slots for p in s for g in p.outputs}
            expected = vm.value('eu5ab_output_price_factor')
            low = vm.value('eu5ab_output_low_weight')
            vm.variables[ACTIVE] = True
            vm.execute(vm.effects[prepare('prices')])
            self.assertEqual(vm.value('eu5ab_output_price_factor'), expected)
            # A skipped stage stays uncomputed, rather than becoming a fake zero.
            self.assertEqual(vm.value('eu5ab_output_low_weight'), low)
            if not market and building == 'mason':
                self.assertEqual(vm.maps[mapping('price_valid')]['building_type:mason'], 3)
                self.assertNotIn('building_type:mason', vm.maps.get(mapping('output_weight_ready'), {}))
            if emergency and price >= 0:
                self.assertEqual(expected, 1)
                self.assertNotIn('building_type:' + building, vm.maps.get(mapping('output_low_weight_ready'), {}))

    def test_typed_upstream_matches_generic_recipe_methods_guarantees_and_markets(self):
        fixture, models = generated_fixture(), cached_game_data()[0]
        vm = UpstreamVM()
        vm.variables.pop(ACTIVE, None)
        generic = parse('test = {\n' + '\n'.join(_upstream_output_shortage_condition_lines(fixture.catalog, RULES, '', True)) + '\n}')[0][2]
        goods = sorted(RULES.input_goods & fixture.catalog.source_buildings_by_good.keys())
        for case in range(10):
            vm.market_exists = case != 0
            vm.native_current = case >= 6
            vm.pending_known = case != 5
            vm.advances = {a for m in models.values() for s in m.slots for p in s for a in p.unlock_advances} if case % 2 else set()
            vm.prices = {g: (0, .8, 1, 2, 1, 1)[case % 6] for g in goods}
            vm.supply = {g: (0, 0, .65, 1, 2, 1)[case % 6] for g in goods}
            vm.demand = {g: 0 if case == 5 else 1 for g in goods}
            for building in _catalog_building_ids(fixture.catalog):
                vm.building = building
                vm.clear()
                vm.maps = {f'eu5ab_native_recipe_slot_{i}': {'building_type:' + building: (0 if case == 6 else len(slot) if case == 7 else 1)}
                           for i, slot in enumerate(models[building].slots) if slot}
                expected = vm.condition(generic)
                self.assertEqual(vm.condition(vm.triggers['eu5ab_upstream_output_shortage']), expected, (building, case))
        block = _blocks_for_token(fixture.triggers, '\neu5ab_upstream_output_shortage = ')[0]
        self.assertNotRegex(block, r'eu5ab_recipe_produces_\w+ = yes')
        self.assertIn('fallback = { always = no }', block)


if __name__ == '__main__':
    unittest.main()
