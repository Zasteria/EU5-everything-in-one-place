"""Diagnostic accounting on the actual generated paths, not timing benchmarks."""
from copy import deepcopy
import unittest

from src.eu5autobuild import scan_probe as probe
from src.eu5autobuild.script_syntax import parse as syntax_parse
from tests._generated import generated_fixture, _blocks_for_token
from tests._governor_script_vm import parse
from tests.test_quote_cache_runtime import QuoteVM
from tests import test_candidate_collection_runtime as collection
from tests import test_candidate_backfill_runtime as backfill

P = probe.PREFIX


class ProbeLogging:
    def execute(self, entries, stack):
        index = 0
        while index < len(entries):
            k, _, v = entries[index]
            end = index + 1
            if k == 'if':
                while end < len(entries) and entries[end][0] in ('else_if', 'else'):
                    end += 1
            if k == 'debug_log':
                self.log.append(v)
            elif k == 'debug_log_date':
                pass  # Wall/game clocks are engine observations, not VM facts.
            elif k.startswith('local_var:') and v == [('debug_log_scopes', '=', 'no')]:
                self.readings.append((self.log[-1], self.value(k, stack)))
            else:
                super().execute(entries[index:end], stack)
            index = end

    def install_probe(self):
        self.log, self.readings = [], []
        self.definitions.update({k: v for k, _, v in parse(probe.render_effects())})

    def command(self, name):
        self.run('eu5ab_probe_scan_' + name, self.ROOT)


class ProbeQuoteVM(ProbeLogging, QuoteVM):
    def __init__(self):
        super().__init__()
        self.install_probe()
        self.vars[self.ROOT].pop('eu5ab_q_active')


class ProbeCollectionVM(ProbeLogging, collection.CollectionVM):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        fixture = generated_fixture()
        self.manual_values = {
            name: parse(_blocks_for_token(fixture.values, '\n' + name + ' = ')[0])[0][2]
            for name in ('eu5ab_manual_policy_value', 'eu5ab_manual_slot_value',
                         'eu5ab_manual_value_global_pause_low_workforce')
        }
        self.manual_month = parse(_blocks_for_token(
            fixture.triggers, '\neu5ab_manual_month_current = ')[0])[0][2]

    def value(self, word, stack):
        if isinstance(word, str):
            if word in self.manual_values:
                return super().value(self.manual_values[word], stack)
            scope, separator, name = word.rpartition('.')
            if separator and name in self.manual_values:
                return self.value(name, stack + [self.target(scope, stack)])
        return super().value(word, stack)

    def test(self, k, op, v, stack):
        if k == 'eu5ab_manual_month_current':
            return self.condition(self.manual_month, stack) == (v == 'yes')
        if k == 'owner' and isinstance(v, str):
            return self.owners.get(stack[-1]) == self.value(v, stack)
        return super().test(k, op, v, stack)


class ProbeBackfillVM(ProbeLogging, backfill.BackfillVM):
    pass


def without_probe(data):
    if isinstance(data, dict):
        return {k: without_probe(v) for k, v in data.items() if not k.startswith(P)}
    return deepcopy(data)


class ScanProbeTests(unittest.TestCase):
    def test_quote_rejection_reasons_are_exclusive_and_acceptance_matches_real_guard(self):
        for case in (*probe.REASONS, 'missing_ticket', 'missing_type', 'cancelled'):
            with self.subTest(case=case):
                vm = ProbeQuoteVM()
                vm.command('start')
                vm.scopes.update(eu5ab_candidate_building='a',
                    eu5ab_quote_ticket=vm.vars['location']['eu5ab_quote_ticket'])
                vm.scopes.update({'eu5ab_engine_' + f: 0 for f in probe.FIELDS})
                expected = case
                if case == 'owner': vm.owners['location'] = 'foreign'
                elif case == 'context': vm.vars[vm.ROOT]['eu5ab_scan_month'] += 1
                elif case == 'ticket': vm.scopes['eu5ab_quote_ticket'] -= 1
                elif case == 'fields': vm.scopes.pop('eu5ab_engine_profit')
                elif case == 'ready':
                    vm.lists['location']['eu5ab_quote_ready_types'] = ['a']
                    vm.lists['location']['eu5ab_quote_requests'].remove('a')
                elif case == 'unrequested': vm.scopes['eu5ab_candidate_building'] = 'c'
                elif case == 'missing_ticket':
                    vm.scopes.pop('eu5ab_quote_ticket'); expected = 'ticket'
                elif case == 'missing_type':
                    vm.scopes.pop('eu5ab_candidate_building'); expected = 'fields'
                elif case == 'cancelled':
                    vm.run('eu5ab_clear_candidate_quotes'); expected = 'context'
                vm.run('eu5ab_gui_capture_candidate_quote')
                state = vm.vars[vm.ROOT]
                self.assertEqual(state[P + 'callbacks'], 1)
                for reason in probe.REASONS:
                    key = 'guard_pass' if reason == 'pass' else 'reject_' + reason
                    self.assertEqual(state[P + key], int(reason == expected))
                self.assertEqual(state[P + 'accepted'], int(expected == 'pass'))

    def test_probe_does_not_change_quote_maps_requests_or_queue_results(self):
        off, on = ProbeQuoteVM(), ProbeQuoteVM()
        on.command('start')
        for vm in (off, on):
            for building in ('a', 'a', 'b', 'b'):
                vm.capture(building)
        for attr in ('vars', 'lists', 'variable_maps'):
            self.assertEqual(without_probe(getattr(off, attr)), without_probe(getattr(on, attr)))
        state = on.vars[on.ROOT]
        self.assertEqual((state[P + 'callbacks'], state[P + 'accepted'], state[P + 'reject_ready']), (4, 2, 2))
        self.assertFalse(any(k.startswith(P) for values in off.vars.values() for k in values))

    def test_gui_windows_preserve_peak_flush_partial_and_bound_trace_output(self):
        vm = ProbeQuoteVM(); vm.command('start'); vm.command('trace')
        state = vm.vars[vm.ROOT]
        for count in (2, 80, 16, *([1] * 33)):
            state[P + 'window_callbacks'] = count
            state[P + 'window_accepted'] = min(2, count)
            vm.command('pulse')
        self.assertEqual(state[P + 'max_callbacks'], 80)
        self.assertEqual(state[P + 'max_accepted'], 2)
        self.assertEqual(state[P + 'windows_ge_16'], 2)
        self.assertEqual(state[P + 'windows_ge_64'], 1)
        self.assertEqual(vm.log.count('EU5AB_SCAN_GUI_WINDOW_BEGIN'), 32)
        state[P + 'window_callbacks'] = 100
        vm.vars['location'][P + 'worker_runs'] = 3
        vm.command('snapshot')
        self.assertIn(('EU5AB_SCAN_MAX_CALLBACKS', 100), vm.readings)
        self.assertIn(('EU5AB_SCAN_WORKER_RUNS', 3), vm.readings)
        self.assertEqual(state[P + 'window_callbacks'], 0)
        vm.command('snapshot')
        self.assertEqual(state[P + 'max_callbacks'], 100)

    def test_stop_and_restart_clear_probe_state_even_after_location_changes_owner(self):
        vm = ProbeQuoteVM(); vm.command('start'); vm.capture('a')
        vm.vars['location'][P + 'ordinary_visits'] = 7
        vm.lists['location'][P + 'ordinary_seen'] = ['a']
        vm.owners['location'] = 'foreign'
        vm.command('stop')
        self.assertFalse(any(k.startswith(P) for values in vm.vars.values() for k in values))
        self.assertFalse(any(v for values in vm.lists.values() for k, v in values.items() if k.startswith(P)))
        vm.owners['location'] = vm.ROOT
        vm.command('start')
        self.assertEqual(vm.vars[vm.ROOT][P + 'callbacks'], 0)

    def test_pool_overlap_cache_paths_and_location_isolation_without_country_writes(self):
        collection.CandidateCollectionRuntimeTests.setUpClass()
        rows = collection.CandidateCollectionRuntimeTests.rows(count=4)
        for row in rows.values():
            row.update({k: True for k, v in row.items() if isinstance(v, bool)})
        for policy, pause in ((100, 1), (1, 1), (100, 0)):
            with self.subTest(policy=policy, pause=pause):
                off = ProbeCollectionVM(deepcopy(collection.CandidateCollectionRuntimeTests.definitions), rows, policy=policy)
                on = ProbeCollectionVM(deepcopy(collection.CandidateCollectionRuntimeTests.definitions), rows, policy=policy)
                on.install_probe(); on.command('start')
                for vm in (off, on):
                    vm.vars[vm.ROOT]['eu5ab_global_pause_low_workforce'] = pause
                country_before = deepcopy(on.vars[on.ROOT])
                for vm in (off, on):
                    vm.run(collection.NORMAL); vm.run(collection.INPUT); vm.run(collection.INPUT)
                self.assertEqual(off.result(), on.result())
                self.assertEqual(off.queries, on.queries)
                self.assertEqual(on.vars[on.ROOT], country_before)
                state = on.vars['location']
                self.assertEqual(state[P + 'ordinary_visits'], 4)
                self.assertEqual(state[P + 'input_visits'], 8)
                self.assertEqual(state[P + 'input_overlap'], 8)
                self.assertEqual(state[P + 'input_repeat'], 4)
                self.assertEqual(state[P + ('input_reuse' if policy == 100 else 'input_native')], 2)
                self.assertEqual(state.get(P + 'workforce_live', 0), 4 if pause else 0)
                self.assertEqual(state.get(P + 'workforce_hit', 0), 8 if pause else 0)
                self.assertEqual(state.get(P + 'workforce_off', 0), 0 if pause else 12)
                on.run(collection.INPUT, 'other')
                self.assertNotIn(P + 'input_overlap', on.vars['other'])
                on.run(collection.CLEAR); on.run(collection.NORMAL)
                self.assertNotIn(P + 'ordinary_repeat', state)

    def test_worker_and_serial_merge_count_once_without_country_writes_from_worker(self):
        backfill.CandidateBackfillRuntimeTests.setUpClass()
        vm = ProbeBackfillVM(deepcopy(backfill.CandidateBackfillRuntimeTests.definitions))
        vm.install_probe(); vm.command('start')
        vm.vars[vm.ROOT].update(eu5ab_scan_month=7, eu5ab_scan_year=1436)
        vm.add_pool('new', 2, inputs=True)
        country_before = deepcopy(vm.vars[vm.ROOT])
        vm.run()
        self.assertEqual(vm.vars['location'][P + 'worker_runs'], 1)
        self.assertEqual(vm.vars[vm.ROOT], country_before)
        vm.run(backfill.MERGE, vm.ROOT); vm.run(backfill.MERGE, vm.ROOT)
        state = vm.vars[vm.ROOT]
        self.assertEqual((state[P + 'merged'], state[P + 'merge_max'], state[P + 'merge_batches']), (1, 1, 1))

    def test_widget_uses_no_native_quote_getters_and_stays_inside_registered_window(self):
        syntax_parse(probe.render_effects()); syntax_parse(probe.render_widget())
        self.assertNotIn('CanBuild', probe.render_widget())
        self.assertNotIn('GetConstruction', probe.render_widget())
        widget = next(content for path, content in generated_fixture().files.items()
                      if path.name == 'eu5ab_engine_queue_window.gui')
        tree = syntax_parse(widget)
        self.assertEqual(len(tree), 1)
        self.assertIn('eu5ab_scan_probe_loop', widget)


if __name__ == '__main__':
    unittest.main()
