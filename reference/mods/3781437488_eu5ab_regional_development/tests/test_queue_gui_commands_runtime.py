"""Pending-item eligibility and native one-shot command wiring.

The script gates run in the existing queue VM. Native visibility/animation
scheduling still requires a game run; the wiring checks do not emulate it.
"""
from copy import deepcopy
import re
import unittest

from src.eu5autobuild.generator import render_engine_queue_gui
from tests import _generated as automation
from tests._governor_script_vm import parse
from tests.test_queue_recovery_runtime import QueueVM


class QueueGuiCommandsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = automation.generated_fixture()
        names = ('eu5ab_gui_queue_candidate_pending', 'eu5ab_gui_queue_profit_pending')
        selected = '\n'.join(automation._blocks_for_token(cls.fixture.scripted_guis, '\n' + name + ' = ')[0]
                             for name in names)
        selected = re.sub(r'saved_scopes = \{[^}]*\}', '', selected)
        cls.gates = {k: dict((name, body) for name, _, body in value)['is_shown']
                     for k, _, value in parse(selected)}

    def setUp(self):
        vm = self.vm = QueueVM(self.fixture.effects, self.fixture.scripted_guis)
        vm.vars[vm.ROOT].update(eu5ab_q_active=1, eu5ab_q_phase=5)
        vm.scopes['eu5ab_engine_queue_check_stage'] = 5
        vm.lists['location']['eu5ab_q_phase_5_types'] = ['building']
        vm.lists[vm.ROOT]['eu5ab_q_phase_5_locations'] = ['location']
        vm.lists[vm.ROOT]['eu5ab_q_phase_5_rgo_locations'] = ['location']
        vm.stubs['eu5ab_reset_engine_candidate_watchdog_progress'] = lambda: None

    def shown(self, kind):
        return self.vm.condition(self.gates[f'eu5ab_gui_queue_{kind}_pending'], ['location'])

    def test_acknowledged_items_stay_hidden_and_real_phase_reset_rearms_them(self):
        vm = self.vm
        self.assertTrue(self.shown('candidate'))
        vm.lists['location']['eu5ab_q_done_types'] = ['building']
        vm.vars['location']['eu5ab_q_done_rgo'] = True
        for _ in range(20):
            self.assertFalse(self.shown('candidate'))
        vm.run('eu5ab_reset_engine_priority_phase_progress', vm.ROOT)
        self.assertTrue(self.shown('candidate'))

    def test_wrong_stage_owner_fire_profit_load_barrier_and_calendar_cannot_send(self):
        vm = self.vm
        before = deepcopy(vm.vars)
        for flag in ('eu5ab_q_fire', 'eu5ab_q_profit_selecting', 'eu5ab_scan_resume_after_load'):
            vm.vars[vm.ROOT][flag] = 1
            self.assertFalse(self.shown('candidate'))
            vm.vars = deepcopy(before)
        for stage in (0, 4, 6, 16, None):
            vm.scopes['eu5ab_engine_queue_check_stage'] = stage
            self.assertFalse(self.shown('candidate'))
        vm.scopes['eu5ab_engine_queue_check_stage'] = 5
        vm.native['eu5ab_queue_calendar_open'] = False
        self.assertFalse(self.shown('candidate'))
        vm.native['eu5ab_queue_calendar_open'] = True
        vm.owners['location'] = 'foreign'
        self.assertFalse(self.shown('candidate'))

    def test_only_the_selected_profit_winner_sends_and_acknowledgement_hides_it(self):
        vm = self.vm
        vm.vars[vm.ROOT]['eu5ab_q_profit_selecting'] = 1
        vm.scopes['eu5ab_engine_queue_check_stage'] = 0
        vm.lists['location']['eu5ab_q_profit_best_types'] = ['building']
        self.assertTrue(self.shown('profit'))
        vm.scopes['eu5ab_candidate_building'] = 'other_building'
        self.assertFalse(self.shown('profit'))
        vm.scopes['eu5ab_candidate_building'] = 'building'
        vm.vars['location']['eu5ab_q_profit_done'] = True
        self.assertFalse(self.shown('profit'))
        vm.run('eu5ab_reset_engine_priority_phase_progress', vm.ROOT)
        self.assertFalse(self.shown('profit'))
        vm.vars[vm.ROOT]['eu5ab_q_profit_selecting'] = 1
        vm.lists['location']['eu5ab_q_profit_best_types'] = ['other_building']
        vm.scopes['eu5ab_candidate_building'] = 'other_building'
        self.assertTrue(self.shown('profit'))

    def test_items_have_one_terminal_show_command_without_a_repeating_broadcast(self):
        gui = render_engine_queue_gui()
        self.assertNotRegex(gui, r"PdxGuiTriggerAllAnimations\('eu5ab_q_(?:validate_candidate|validate_rgo|profit_validate_candidate)")
        # Finite readers sample inputs once. Pure script owns completion.
        self.assertNotIn('name = eu5ab_q_validate_check_5', gui)
        self.assertIn("PdxGuiTriggerAllAnimations('eu5ab_bridge_candidate_1_parallel_sample')", gui)
        self.assertNotIn("PdxGuiTriggerAllAnimations('eu5ab_q_confirm_build')", gui)
        self.assertNotIn("GetScriptedGui('eu5ab_gui_queue_sync_check').Execute", gui)
        self.assertNotIn("GetScriptedGui('eu5ab_gui_queue_confirm_sync').Execute", gui)
        self.assertNotIn("GetScriptedGui('eu5ab_gui_queue_confirm_candidate').Execute", gui)
        entries = parse(re.sub(r'(?:size|position) = \{ [-\d ]+ \}', '', gui))
        items = []

        def walk(entries):
            for key, _, value in entries:
                if not isinstance(value, list):
                    continue
                if key == 'widget':
                    props = dict((k, v) for k, _, v in value)
                    states = [dict((k, v) for k, _, v in body) for k, _, body in value if k == 'state']
                    if any('eu5ab_gui_queue_try_' in state.get('on_finish', '') for state in states):
                        items.append((props, states))
                walk(value)

        walk(entries)
        self.assertEqual(len(items), 4)  # Ordinary/profit readers, two alternating lanes.
        self.assertNotIn('eu5ab_gui_queue_try_rgo', gui)
        self.assertNotIn('eu5ab_q_probe_approved', gui)
        for props, states in items:
            self.assertEqual(props['visible_at_creation'], 'no')
            self.assertEqual(props['visible'], '[GetPlayer.Exists]')
            self.assertEqual([state['name'] for state in states[:2]], ['_hide', '_show'])
            self.assertNotIn('on_finish', states[0])
            self.assertNotIn('next', states[0])
            self.assertNotIn('next', states[1])
            self.assertIn('eu5ab_bridge_ticket', states[2]['on_finish'])
        self.assertNotIn('eu5ab_gui_queue_candidate_pending', gui)
        self.assertNotIn('eu5ab_gui_queue_profit_pending', gui)
        self.assertNotIn("GetList('eu5ab_q_phase_", gui)

    def test_approved_script_list_is_acknowledged_once_without_a_gui_round(self):
        vm = self.vm
        vm.lists['location']['eu5ab_q_approved_types'] = ['building']
        vm.run('eu5ab_acknowledge_approved_engine_candidate', 'location')
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_seen'], 1)
        for _ in range(20):
            vm.run('eu5ab_acknowledge_approved_engine_candidate', 'location')
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_seen'], 1)
        self.assertEqual(vm.lists['location']['eu5ab_q_seen_types'], ['building'])
        vm.scopes['eu5ab_candidate_building'] = 'unapproved'
        vm.run('eu5ab_acknowledge_approved_engine_candidate', 'location')
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_seen'], 1)


if __name__ == '__main__':
    unittest.main()
