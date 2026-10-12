"""Generated GUI lifecycle contract + generated-effect liveness regression tests.

This models the documented GUI timer semantics, not the native rendering engine.
It deliberately does not use GovernorScriptVM.finish(), which bypasses the driver.
"""
import re
import unittest

from src.eu5autobuild.governor_layout_liveness import PROGRESS_FIELDS
from src.eu5autobuild.governor_layout_ui import (
    render_layout_scripted_guis, render_layout_worker_gui,
)
from src.eu5autobuild.governor_planner import NAVAL_PLANNER
from src.eu5autobuild.generator import render_scripted_windows
from tests._governor_script_vm import GovernorScriptVM, parse
from tests.test_governor_layout_policy import locations


def fields(entries):
    return {key: value for key, _, value in entries}


class WorkerTimers:
    def __init__(self, vm, player=True):
        self.vm, self.player = vm, player
        self.guis = {key: fields(value) for key, _, value in parse(render_layout_scripted_guis() + render_layout_scripted_guis(NAVAL_PLANNER))}
        self.timers = []
        self.senders = {}
        self.pending = []
        self.time = 0
        self.blocked = set()
        # Geometry vectors are not effect blocks and do not affect scheduling.
        gui_text = re.sub(r"size = \{ 0 0 \}", "", render_layout_worker_gui())
        # Only registered roots are instantiated by the game. Loading every
        # widget definition hid a missing registration for the naval worker.
        registered = re.findall(
            r"^gui/eu5ab_governor_worker\.gui\s*=\s*(\w+)",
            render_scripted_windows(), re.M,
        )
        root = [item for key, _, value in parse(gui_text)
                if key == "widget" and fields(value)["name"] in registered
                for item in value]
        for key, _, child in root:
            if key != "widget":
                continue
            props = fields(child)
            if props["visible"] != "[GetPlayer.Exists]":
                raise AssertionError("Unexpected layout visibility trigger")
            if props["visible_at_creation"] != "no":
                raise AssertionError("Layout window visible at creation")
            states = {fields(s)["name"]: fields(s) for k, _, s in child if k == "state"}
            init = next(s for s in states.values() if s.get("trigger_on_create") == "yes")
            # A permanent true trigger can repeatedly restart the delay.
            if any("trigger_when" in s for s in states.values()):
                raise AssertionError("Layout state has a permanent restart trigger")
            # Native EU5 logs "no valid state properties" and discards pure
            # timer states. Model that requirement instead of assuming next runs.
            if not all("alpha" in s for s in states.values()):
                raise AssertionError("Layout timer state lacks alpha")
            # Creation of an already-active save: do not synthesize _show.
            self.timers.append([states, init["name"], float(init["duration"])])
            # The persistent timer broadcasts an animation; a guarded child
            # sends the script command. Native scheduling is still injected.
            for name, _, sender in child:
                if name != 'widget':
                    continue
                model = fields(sender)['datamodel']
                gui = re.search(r"GetScriptedGui\('([^']+)'\)", model)[1]
                item = fields(fields(sender)['item'])['widget']
                for kind, _, state in item:
                    if kind == 'state' and 'on_finish' in fields(state):
                        state = fields(state)
                        command = re.search(r"GetScriptedGui\('([^']+)'\)", state['on_finish'])[1]
                        assert gui == command
                        self.senders[state['name']] = (gui, float(state['duration']))

    def deliver(self, name):
        gui = self.guis[name]
        if name not in self.blocked and self.vm.condition(gui['is_valid'], [self.vm.ROOT]):
            self.vm.local, self.vm.scopes, self.vm.operations = {}, {}, 0
            self.vm.execute(gui['effect'], [self.vm.ROOT])

    def advance(self, seconds):
        for _ in range(round(seconds * 10)):
            self.time += .1
            if not self.player:
                continue
            ready = [name for due, name in self.pending if due <= self.time]
            self.pending = [(due, name) for due, name in self.pending if due > self.time]
            for name in ready:
                self.deliver(name)
            for timer in self.timers:
                states, current, remaining = timer
                remaining -= 0.1
                if remaining <= 0.0001:
                    state = states[current]
                    if "on_finish" in state:
                        animation = re.search(r"PdxGuiTriggerAllAnimations\('([^']+)'\)", state['on_finish'])[1]
                        name, delay = self.senders[animation]
                        if self.vm.condition(self.guis[name]['is_shown'], [self.vm.ROOT]):
                            self.pending.append((self.time + delay, name))
                    current = state["next"]
                    remaining = float(states[current]["duration"])
                timer[1:] = [current, remaining]


class LayoutLivenessTests(unittest.TestCase):
    def fixture(self):
        nodes = locations(5)
        vm = GovernorScriptVM(nodes, {}, {}, {0: 100, 1: 80}, {1}, {2, 3, 4}, 0)
        return vm, vm.vars[vm.ROOT]

    def test_created_with_active_save_runs_without_show_edge_or_game_day(self):
        vm, root = self.fixture()
        vm.call("eu5ab_layout_begin")
        worker = WorkerTimers(vm)
        worker.advance(30)
        self.assertNotIn("eu5ab_governor_scan_active", root)
        self.assertNotIn("eu5ab_layout_failed", root)
        self.assertEqual(root["eu5ab_layout_candidate_count"], 3)
        self.assertNotIn("eu5ab_layout_liveness_ready", root)
        self.assertEqual(len(vm.scheduled_events), 1)  # No daily event was executed.

    def test_player_late_background_restart_and_second_run_need_no_active_edge(self):
        vm, root = self.fixture()
        worker = WorkerTimers(vm, player=False)
        worker.advance(1)
        worker.player = True
        worker.advance(1)  # Idle before the first automatic request.
        for _ in range(2):
            vm.call("eu5ab_layout_begin")
            worker.advance(0.4)
            self.assertGreater(root["eu5ab_layout_ticks"], 0)
            vm.call("eu5ab_layout_abort")
            vm.call("eu5ab_layout_begin")  # clear/set in one frame
            worker.advance(30)
            self.assertNotIn("eu5ab_governor_scan_active", root)
            self.assertNotIn("eu5ab_layout_failed", root)
            self.assertEqual(root["eu5ab_layout_candidate_count"], 3)

    def test_separate_timer_fails_stopped_pulse_chain_and_retry_recovers(self):
        vm, root = self.fixture()
        vm.call("eu5ab_layout_begin")
        worker = WorkerTimers(vm)
        worker.blocked.add("eu5ab_gui_layout_tick")
        worker.advance(11)
        self.assertIn("eu5ab_layout_failed", root)
        self.assertNotIn("eu5ab_governor_scan_active", root)
        self.assertNotIn("eu5ab_governor_manual_run", root)
        self.assertNotIn("eu5ab_layout_liveness_ready", root)
        # Manual retry succeeds even with the GUI pulse chain still blocked.
        vm.call("eu5ab_governor_manual_recalculation")
        self.assertNotIn("eu5ab_layout_failed", root)
        self.assertNotIn("eu5ab_governor_scan_active", root)
        self.assertEqual(root["eu5ab_layout_candidate_count"], 3)

    def test_manual_returns_complete_without_any_gui_or_date_callback(self):
        vm, root = self.fixture()
        root.update(eu5ab_global_governor_recommendations_enabled=0,
                    eu5ab_global_governor_migration_enabled=0)
        for _ in range(2):
            vm.call("eu5ab_governor_manual_recalculation")
            self.assertNotIn("eu5ab_governor_scan_active", root)
            self.assertNotIn("eu5ab_governor_manual_run", root)
            self.assertNotIn("eu5ab_layout_failed", root)
            self.assertEqual(root["eu5ab_layout_candidate_count"], 3)
            self.assertEqual(root["eu5ab_global_governor_migration_enabled"], 0)

    def test_manual_no_work_callback_and_exhausted_budget_fail_without_pending_job(self):
        for fault in ("no_work", "budget"):
            with self.subTest(fault=fault):
                vm, root = self.fixture()
                if fault == "no_work":
                    vm.definitions["eu5ab_layout_tick"] = parse(
                        "change_variable = { name = eu5ab_layout_ticks add = 1 }")
                else:
                    finish = vm.definitions["eu5ab_layout_finish_manual"]
                    branch = next(value for key, _, value in finish if key == "if")
                    loop = next(value for key, _, value in branch if key == "while")
                    loop[:] = [(key, op, "1" if key == "count" else value) for key, op, value in loop]
                vm.call("eu5ab_governor_manual_recalculation")
                self.assertIn("eu5ab_layout_failed", root)
                self.assertNotIn("eu5ab_governor_scan_active", root)
                self.assertNotIn("eu5ab_governor_manual_run", root)
                self.assertNotIn("eu5ab_layout_has_results", root)

    def test_callback_count_alone_does_not_prove_progress(self):
        vm, root = self.fixture()
        vm.call("eu5ab_layout_begin")
        for count in (100, 200):
            root["eu5ab_layout_ticks"] = count
            vm.call("eu5ab_layout_check_liveness")
        self.assertIn("eu5ab_layout_failed", root)

    def test_every_useful_progress_field_resets_stall_guard(self):
        for field in PROGRESS_FIELDS:
            with self.subTest(field=field):
                vm, root = self.fixture()
                vm.call("eu5ab_layout_begin")
                vm.call("eu5ab_layout_check_liveness")
                self.assertEqual(root["eu5ab_layout_stalled_checks"], 1)
                root[field] += 1
                vm.call("eu5ab_layout_check_liveness")
                self.assertEqual(root["eu5ab_layout_stalled_checks"], 0)
                self.assertNotIn("eu5ab_layout_failed", root)

    def test_old_save_observation_grace_and_idle_observer_are_safe(self):
        vm, root = self.fixture()
        vm.call("eu5ab_layout_check_liveness")
        self.assertNotIn("eu5ab_layout_liveness_ready", root)
        vm.call("eu5ab_layout_begin")
        vm.call("eu5ab_layout_clear_liveness")
        vm.call("eu5ab_layout_check_liveness")
        self.assertEqual(root["eu5ab_layout_stalled_checks"], 0)
        vm.call("eu5ab_layout_tick")
        vm.call("eu5ab_layout_check_liveness")
        self.assertEqual(root["eu5ab_layout_stalled_checks"], 0)

    def test_native_timer_states_have_properties_and_no_permanent_retrigger(self):
        gui = render_layout_worker_gui()
        states = re.findall(r"state = \{([^{}]+)\}", gui)
        self.assertTrue(states)
        for state in states:
            self.assertRegex(state, r"\balpha = [01]\b")
            if 'on_finish' in state or 'trigger_on_create' in state:
                self.assertIn('duration =', state)
            self.assertNotIn("trigger_when", state)


if __name__ == "__main__":
    unittest.main()
