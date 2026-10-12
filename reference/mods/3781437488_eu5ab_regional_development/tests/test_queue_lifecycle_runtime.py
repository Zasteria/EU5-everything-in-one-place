"""Delayed callbacks must not time out a different queue stage.

Callbacks are injected; the native GUI animation scheduler is not emulated.
"""
from copy import deepcopy
import re
import unittest

from src.eu5autobuild.generator import render_engine_queue_gui
from tests._governor_script_vm import parse
from tests.test_queue_recovery_runtime import profit_queue_vm


class QueueLifecycleRuntimeTests(unittest.TestCase):
    def vm(self):
        vm = profit_queue_vm()
        vm.vars[vm.ROOT].update(eu5ab_q_expected=21, eu5ab_q_processed=0,
                               eu5ab_q_seen=0, eu5ab_q_progress_last=0,
                               eu5ab_q_stall_rounds=0)
        vm.stubs['eu5ab_finish_engine_candidate_queue'] = lambda: vm.calls.append('finish')
        return vm

    def test_stale_or_untagged_checks_leave_the_current_stage_unchanged(self):
        for profit_selection, sources in ((True, (5, None)), (False, (0, 1, 4, 6, 16))):
            for source in sources:
                with self.subTest(profit_selection=profit_selection, source=source):
                    vm = self.vm()
                    if not profit_selection:
                        vm.vars[vm.ROOT].pop('eu5ab_q_profit_selecting')
                    if source is None:
                        vm.scopes.pop('eu5ab_engine_queue_check_stage', None)
                    else:
                        vm.scopes['eu5ab_engine_queue_check_stage'] = source
                    before = deepcopy(vm.vars)
                    for _ in range(12):
                        vm.run('eu5ab_gui_queue_sync_check', vm.ROOT)
                    self.assertEqual(vm.vars, before)
                    self.assertEqual(vm.calls, [])

    def test_current_profit_checks_still_have_bounded_timeout(self):
        vm = self.vm()
        vm.scopes['eu5ab_engine_queue_check_stage'] = 0
        for _ in range(12):
            vm.run('eu5ab_gui_queue_sync_check', vm.ROOT)
        self.assertEqual(vm.calls, ['finish'])
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_diag_queue_state'], 5)

    def test_transition_check_does_not_spend_new_stage_timeout(self):
        vm = self.vm()
        vm.vars[vm.ROOT].pop('eu5ab_q_profit_selecting')
        vm.vars[vm.ROOT].update(eu5ab_q_processed=244, eu5ab_q_expected=244,
                               eu5ab_global_candidate_ranking_mode=2)
        vm.scopes['eu5ab_engine_queue_check_stage'] = 5

        def transition():
            vm.vars[vm.ROOT].update(eu5ab_q_profit_selecting=True,
                                   eu5ab_q_expected=21, eu5ab_q_processed=0,
                                   eu5ab_q_stall_rounds=0)

        vm.stubs['eu5ab_prepare_actual_profit_selection'] = transition
        vm.run('eu5ab_gui_queue_sync_check', vm.ROOT)
        self.assertTrue(vm.vars[vm.ROOT]['eu5ab_q_profit_selecting'])
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_stall_rounds'], 0)

    def test_current_phase_check_still_advances_completed_phase(self):
        vm = self.vm()
        vm.vars[vm.ROOT].pop('eu5ab_q_profit_selecting')
        vm.vars[vm.ROOT].update(eu5ab_q_processed=21,
                               eu5ab_global_candidate_ranking_mode=0)
        vm.scopes['eu5ab_engine_queue_check_stage'] = 5

        def advance():
            vm.calls.append('advance')
            vm.vars[vm.ROOT].update(eu5ab_q_phase=6, eu5ab_q_stall_rounds=0)

        vm.stubs['eu5ab_advance_engine_priority_phase'] = advance
        vm.run('eu5ab_gui_queue_sync_check', vm.ROOT)
        self.assertEqual(vm.calls, ['advance'])
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_stall_rounds'], 0)

    def test_data_completion_advances_without_a_gui_check_or_timeout_charge(self):
        vm = self.vm()
        vm.vars[vm.ROOT].pop('eu5ab_q_profit_selecting')
        vm.vars[vm.ROOT].update(eu5ab_q_processed=21,
                               eu5ab_global_candidate_ranking_mode=0)
        vm.scopes.pop('eu5ab_engine_queue_check_stage', None)
        vm.stubs['eu5ab_advance_engine_priority_phase'] = lambda: vm.calls.append('advance')
        vm.run('eu5ab_check_engine_phase_completion', vm.ROOT)
        self.assertEqual(vm.calls, ['advance'])
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_q_stall_rounds'], 0)

    def test_early_data_completion_is_idle_and_cannot_spend_a_timeout(self):
        vm = self.vm()
        before = deepcopy(vm.vars)
        for _ in range(20):
            vm.run('eu5ab_check_engine_phase_completion', vm.ROOT)
        self.assertEqual(vm.vars, before)
        self.assertEqual(vm.calls, [])

    def test_confirmation_completion_has_fire_calendar_and_load_barriers(self):
        for barrier in ('before_fire', 'load', 'calendar'):
            vm = self.vm()
            vm.vars[vm.ROOT].update(eu5ab_q_confirmed=1, eu5ab_q_approved=1)
            if barrier != 'before_fire': vm.vars[vm.ROOT]['eu5ab_q_fire'] = 1
            if barrier == 'load': vm.vars[vm.ROOT]['eu5ab_scan_resume_after_load'] = 1
            if barrier == 'calendar': vm.native['eu5ab_queue_calendar_open'] = False
            before = deepcopy(vm.vars)
            vm.run('eu5ab_check_engine_confirmation_completion', vm.ROOT)
            self.assertEqual(vm.vars, before)

    def test_native_confirmation_completion_advances_once_without_a_gui_pulse(self):
        vm = self.vm()
        vm.vars[vm.ROOT].update(eu5ab_q_fire=1, eu5ab_q_confirmed=1, eu5ab_q_approved=1,
                               eu5ab_q_processed=21)
        def advance():
            vm.calls.append('advance')
            vm.vars[vm.ROOT].pop('eu5ab_q_fire')
        vm.stubs['eu5ab_advance_engine_priority_phase'] = advance
        vm.run('eu5ab_check_engine_confirmation_completion', vm.ROOT)
        vm.run('eu5ab_check_engine_confirmation_completion', vm.ROOT)
        self.assertEqual(vm.calls, ['advance'])

    def test_native_controller_lifecycle_and_check_source_are_wired(self):
        # Validate the native wiring that this script VM cannot execute. Hidden
        # controllers need a terminal state, and duration-only states may be
        # discarded by the engine. Alpha belongs to zero-size controllers.
        gui = re.sub(r'(?:size|position) = \{ [-\d ]+ \}', '', render_engine_queue_gui())
        controllers = []

        def walk(entries):
            for key, _, value in entries:
                if not isinstance(value, list):
                    continue
                props = {k: v for k, _, v in value}
                shown = props.get('visible', '')
                if any(k == 'state' and any(a == 'next' and str(c).startswith('eu5ab_bridge_') for a, _, c in body)
                       for k, _, body in value):
                    controllers.append((props, [v for k, _, v in value if k == 'state']))
                walk(value)

        walk(parse(gui))
        self.assertEqual(len(controllers), 10)  # Five transport kinds, alternating lanes.
        stages = []
        for props, raw_states in controllers:
            states = {dict((k, v) for k, _, v in state)['name']:
                      dict((k, v) for k, _, v in state) for state in raw_states}
            self.assertIn('next', states['_show'])
            self.assertEqual(props['visible_at_creation'], 'no')
            for state in states.values():
                self.assertIn('alpha', state)
                if 'next' in state:
                    self.assertIn(state['next'], states)
            self.assertNotIn('next', states['_hide'])
            self.assertNotIn('on_finish', states['_hide'])
            for action in (value for raw in raw_states for key, _, value in raw if key == 'on_finish'):
                if "GetScriptedGui('eu5ab_gui_refresh_planning_queue')" in action:
                    stage = re.search(r"AddScope\('eu5ab_engine_queue_check_stage', MakeScopeValue\('\(CFixedPoint\)(-?\d+)'\)\)", action)
                    self.assertIsNotNone(stage)
                    stages.append(int(stage[1]))
        self.assertEqual(stages, [])
        self.assertNotIn("GetScriptedGui('eu5ab_gui_refresh_planning_queue').Execute", gui)


if __name__ == '__main__':
    unittest.main()
