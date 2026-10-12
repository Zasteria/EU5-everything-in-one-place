"""Unbatched quote readers and early native-read guards, without a GUI scheduler."""
from copy import deepcopy
import re
import unittest
from unittest.mock import patch

from src.eu5autobuild import quote_cache
from tests import _gui_callbacks as gui
from tests._generated import generated_fixture, _blocks_for_token
from tests._governor_script_vm import parse
from tests.test_quote_cache_runtime import QuoteVM

# Verified against the installed game's 1.3.11 data_types dumps.
API = {
    'Scope.GetBuildingType': [['Promote', 'BuildingType']],
    'Scope.GetVariable': [['Promote', 'Scope']],
    'BuildingType.MakeScope': [['Promote', 'Scope'], ['Function', 'Scope']],
    'BuildingType.Self': [['Function', '[unregistered]']],
    'BuildingType.GetObsoleteBuildingInLocation': [['Promote', 'Building']],
    'MakeScopeBool': [['Global function', 'Scope']],
    'Add_CFixedPoint': [['Global function', 'CFixedPoint']],
    'CanBuildOrExpandBuilding': [['Global function', 'bool']],
    'GetBuildOrExpandBuildingCost': [['Global function', 'CFixedPoint']],
    'GetBuildingTypeIncomeToOwnerInLocation': [['Global function', 'CFixedPoint']],
    'GetBuildingTypeProfitInLocation': [['Global function', 'CFixedPoint']],
    'Location.GetProvince': [['Promote', 'Province']],
    'Province.GetMonthlyFood': [['Function', 'CFixedPoint']],
    'Province.GetFoodFromMarket': [['Function', 'CFixedPoint']],
    'Location.GetRawMaterialsPrice': [['Function', 'CFixedPoint']],
    'Location.Self': [['Function', '[unregistered]']],
    'Country.Self': [['Function', '[unregistered]']],
}


class QuoteBridge(gui.GuiBridge):
    """Native quote values are injected; gates and callback effects are real."""
    def __init__(self, vm):
        super().__init__(vm)
        self.reads = []
        source = re.sub(r'saved_scopes = \{[^}]*\}', '', quote_cache.render_guis())
        self.guis = {k: dict((a, c) for a, _, c in v) for k, _, v in parse(source)}
        self.guis['eu5ab_gui_capture_candidate_quote'] = dict(
            (k, v) for k, _, v in vm.definitions['eu5ab_gui_capture_candidate_quote'])

    def eval(self, node, context):
        if isinstance(node, list):
            names = [name for name, _ in node]
            native = {
                'GetBuildOrExpandBuildingCost': 100,
                'GetBuildingTypeIncomeToOwnerInLocation': 12,
                'GetBuildingTypeProfitInLocation': 10,
                'CanBuildOrExpandBuilding': True,
                'GetMonthlyFood': 0,
                'GetFoodFromMarket': 0,
                'GetRawMaterialsPrice': 0,
                'GetObsoleteBuildingInLocation': 'old',
            }
            for name, value in native.items():
                if name in names:
                    self.reads.append((context['Location'], context['BuildingType'], name))
                    return value
            if names == ['Add_CFixedPoint']:
                return sum(self.eval(arg, context) for arg in node[0][1])
        return super().eval(node, context)


class QuoteReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = generated_fixture()
        text = cls.fixture.engine_queue_gui
        start = text.rfind('widget = {', 0, text.index('name = "eu5ab_quote_reader_root"'))
        cls.widget = _blocks_for_token(text[start:], 'widget = ')[0]

    def quotes(self, types=('a',)):
        vm = QuoteVM(types)
        vm.vars[vm.ROOT].pop('eu5ab_q_active')
        return vm

    def test_all_pending_quotes_are_read_and_missing_receipt_does_not_block_new_rows(self):
        vm = self.quotes(tuple(f'type_{i}' for i in range(19)))
        vm.pool(['location', 'second'], [list(vm.lists['location']['eu5ab_quote_requests']), ['x', 'y', 'z']])
        vm.run('eu5ab_request_candidate_quotes', 'second')
        # Withdrawn projections in existing saves are ignored. No publisher or
        # load migration is needed to read the authoritative pending requests.
        vm.lists[vm.ROOT]['eu5ab_quote_read_locations'] = ['location']
        vm.lists['location']['eu5ab_quote_read_types'] = ['type_0']
        vm.lists['location']['eu5ab_quote_read_tickets'] = [-1]
        with patch.dict(gui.API, API):
            bridge = QuoteBridge(vm)
            # Inject original _show activation, without emulating native timing.
            commands = bridge.callbacks(self.widget, None, animation='eu5ab_quote_capture')
            self.assertEqual(len(commands), 22)
            for command in commands[1:]:
                bridge.deliver(command)
            self.assertEqual(vm.lists['location']['eu5ab_quote_requests'], ['type_0'])
            self.assertFalse(vm.lists['second']['eu5ab_quote_requests'])
            vm.pool(['third'], [['new_a', 'new_b']])
            vm.run('eu5ab_request_candidate_quotes', 'third')
            next_commands = bridge.callbacks(self.widget, None, animation='eu5ab_quote_capture')
            self.assertCountEqual([(args['root'], args['scopes']['eu5ab_candidate_building'])
                                  for _, args in next_commands],
                                 [('location', 'type_0'), ('third', 'new_a'), ('third', 'new_b')])
            for command in next_commands:
                bridge.deliver(command)
            self.assertFalse(vm.lists[vm.ROOT]['eu5ab_quote_pending_locations'])
            before = deepcopy((vm.vars, vm.lists, vm.variable_maps))
            bridge.deliver(commands[0])
            self.assertEqual((vm.vars, vm.lists, vm.variable_maps), before)

    def test_completed_and_invalid_rows_do_not_evaluate_native_getters(self):
        for change in ('ready', 'unrequested', 'owner', 'month', 'recovery'):
            with self.subTest(change=change), patch.dict(gui.API, API):
                vm = self.quotes()
                bridge = QuoteBridge(vm)
                commands = bridge.callbacks(self.widget, None, animation='eu5ab_quote_capture')
                self.assertEqual(len(commands), 1)
                if change == 'ready': vm.lists['location']['eu5ab_quote_ready_types'] = ['a']
                elif change == 'unrequested': vm.lists['location']['eu5ab_quote_requests'] = []
                elif change == 'owner': vm.owners['location'] = 'foreign'
                elif change == 'recovery': vm.vars[vm.ROOT]['eu5ab_scan_resume_after_load'] = True
                else: vm.vars[vm.ROOT]['eu5ab_scan_month'] += 1
                reads = len(bridge.reads)
                self.assertEqual(bridge.callbacks(self.widget, None, animation='eu5ab_quote_capture'), [])
                self.assertEqual(len(bridge.reads), reads)
                if change == 'recovery':
                    before = deepcopy((vm.vars, vm.lists, vm.variable_maps))
                    bridge.deliver(commands[0])
                    self.assertEqual((vm.vars, vm.lists, vm.variable_maps), before)

    def test_show_does_not_read_and_old_ticket_row_cannot_read_a_new_request(self):
        with patch.dict(gui.API, API):
            vm = self.quotes()
            bridge = QuoteBridge(vm)
            self.assertEqual(bridge.callbacks(self.widget, None, animation='_show'), [])
            self.assertEqual(bridge.reads, [])
            old_ticket = vm.vars['location']['eu5ab_quote_ticket']
            old_command = bridge.callbacks(self.widget, None, animation='eu5ab_quote_capture')[0]
            vm.run('eu5ab_clear_candidate_quotes', 'location')
            vm.run('eu5ab_request_candidate_quotes', 'location')
            new_ticket = vm.vars['location']['eu5ab_quote_ticket']
            self.assertGreater(new_ticket, old_ticket)
            # Retain an old numeric row as a native animation might do. Its
            # guard must reject it before constructing any getter expression.
            start = self.widget.rfind('widget = {', 0,
                self.widget.index("GetScriptedGui('eu5ab_gui_quote_request_pending')"))
            row = _blocks_for_token(self.widget[start:], 'widget = ')[0]
            reads = len(bridge.reads)
            self.assertEqual(bridge.callbacks(row, old_ticket,
                animation='eu5ab_quote_capture', Location='location', BuildingType='a'), [])
            self.assertEqual(len(bridge.reads), reads)
            before = deepcopy((vm.vars, vm.lists, vm.variable_maps))
            bridge.deliver(old_command)
            self.assertEqual((vm.vars, vm.lists, vm.variable_maps), before)
            command = bridge.callbacks(self.widget, None, animation='eu5ab_quote_capture')[0]
            self.assertEqual(command[1]['scopes']['eu5ab_quote_ticket'], new_ticket)
            bridge.deliver(command)
            self.assertEqual(vm.lists['location']['eu5ab_quote_ready_types'], ['a'])

    def test_missing_ticket_projection_is_repaired_without_clearing_ready_quotes(self):
        vm = self.quotes(('a', 'b'))
        vm.capture('a')
        vm.lists['location']['eu5ab_quote_tickets'] = []
        before = deepcopy((vm.vars, vm.variable_maps, vm.lists['location']))
        # Exercise the emitted load hook, isolating it from unrelated queue
        # recovery. This is the consumer required by saves without ticket rows.
        recovery = parse(_blocks_for_token(self.fixture.effects,
            '\neu5ab_recover_runtime_after_load = ')[0])[0][2]
        vm.definitions['restore_quote_reader'] = [
            next(entry for entry in recovery if entry[:2] == ('save_scope_as', '=')
                 and entry[2] == 'eu5ab_quote_restore_country'),
            next(entry for entry in recovery if entry[0] == 'every_in_list'
                 and ('variable', '=', 'eu5ab_quote_pending_locations') in entry[2]),
        ]
        vm.run('restore_quote_reader', vm.ROOT)
        self.assertEqual(vm.vars, before[0])
        self.assertEqual(vm.variable_maps, before[1])
        expected = before[2]
        expected['eu5ab_quote_tickets'] = [vm.vars['location']['eu5ab_quote_ticket']]
        self.assertEqual(vm.lists['location'], expected)
        with patch.dict(gui.API, API):
            commands = QuoteBridge(vm).callbacks(self.widget, None, animation='eu5ab_quote_capture')
        self.assertEqual([args['scopes']['eu5ab_candidate_building'] for _, args in commands], ['b'])

    def test_unavailable_player_never_constructs_readers_or_reads_pending_lists(self):
        with patch.dict(gui.API, API):
            bridge = QuoteBridge(self.quotes())
            self.assertEqual(bridge.callbacks(self.widget, None,
                animation='eu5ab_quote_capture', player='missing'), [])
            self.assertEqual(bridge.country_reads, [])
            self.assertEqual(bridge.reads, [])

    def test_generated_readers_have_no_withdrawn_batch_controller_or_recovery_hooks(self):
        with patch.dict(gui.API, API):
            gui.check_widget(self.widget)
        self.assertEqual(self.widget.count('CanBuildOrExpandBuilding'), 1)
        text = self.fixture.effects + self.fixture.scripted_guis + self.fixture.engine_queue_gui
        for token in ('eu5ab_quote_read_', 'eu5ab_capacity_read_', 'eu5ab_scan_read_',
                      'eu5ab_publish_scan_read_batches', 'eu5ab_clear_scan_read_batches'):
            self.assertNotIn(token, text)
        self.assertIn("GetList('eu5ab_worker_pending_locations')", self.fixture.engine_queue_gui)
        self.assertIn('name = eu5ab_capacity_capture_loop', self.fixture.engine_queue_gui)


if __name__ == '__main__':
    unittest.main()
