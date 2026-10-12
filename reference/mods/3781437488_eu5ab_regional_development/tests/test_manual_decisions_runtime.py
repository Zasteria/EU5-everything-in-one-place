"""Execute decision state transitions; native GUI rendering remains an in-game check."""
from copy import deepcopy
from functools import cache
from pathlib import Path
import json
import re
import unittest

from src.eu5autobuild import manual_decisions, monthly_schedule
from src.eu5autobuild.queue_bridge import _block
from src.eu5autobuild.script_syntax import parse as syntax_parse
from tests._generated import _blocks_for_token, generated_fixture
from tests._governor_script_vm import parse
from tests._gui_callbacks import expression
from tests.test_construction_batch_runtime import BatchVM
from tests.test_rgo_batch_runtime import RgoBatchVM


@cache
def definitions():
    f = generated_fixture()
    names = re.findall(r'^(eu5ab_(?:manual|profile)_\w+) = \{', f.effects, re.M)
    return {k: v for k, _, v in parse('\n'.join(_block(f.effects, n) for n in names))}


class ManualVM(BatchVM):
    def __init__(self):
        super().__init__()
        self.definitions.update(definitions())
        f = generated_fixture()
        self.definitions.update({k: v for k, _, v in parse(_block(f.effects, 'eu5ab_record_scan_date'))})
        self.capacity_triggers.update({k: v for k, _, v in parse(
            monthly_schedule.render_triggers() + manual_decisions.render_triggers()
            + _block(f.triggers, 'eu5ab_manual_physical_calendar')
            + _block(f.triggers, 'eu5ab_queue_calendar_open'))})
        for key in ('eu5ab_manual_month_current', 'eu5ab_manual_physical_calendar', 'eu5ab_queue_calendar_open'):
            self.native.pop(key, None)
        for key in ('eu5ab_global_budget_limit_value', 'eu5ab_manual_policy_value', 'eu5ab_manual_slot_value'):
            self.capacity_values.update({k: v for k, _, v in parse(_block(f.values, key))})
        self.humans = {self.ROOT}
        self.day, self.month_number, self.year = 12, 5, 1436
        self.vars[self.ROOT].update(eu5ab_scan_month=5, eu5ab_scan_year=1436)
        self.scopes['eu5ab_engine_country'] = self.ROOT
        self.scheduled = []
        self.globals = {}
        self.stubs['eu5ab_finish_engine_candidate_queue_live'] = lambda: self.vars[self.ROOT].pop('eu5ab_q_active', None)

    def test(self, k, op, v, stack):
        if k == 'is_human': return (stack[-1] in self.humans) == (v == 'yes')
        if k == 'custom_tooltip': return self.condition([e for e in v if e[0] != 'text'], stack)
        if k == 'has_global_variable': return v in self.globals
        return super().test(k, op, v, stack)

    def value(self, x, stack):
        if isinstance(x, str) and x.startswith('global_var:'): return self.globals[x.split(':', 1)[1]]
        return super().value(x, stack)

    def execute(self, entries, stack):
        index = 0
        while index < len(entries):
            k, op, v = entries[index]
            end = index + 1
            if k == 'if':
                while end < len(entries) and entries[end][0] in ('else_if', 'else'): end += 1
            if k in ('set_global_variable', 'change_global_variable'):
                data = dict((a, b) for a, _, b in v)
                if k == 'set_global_variable': self.globals[data['name']] = self.value(data['value'], stack)
                else: self.globals[data['name']] += self.value(data['add'], stack)
            elif k == 'every_key_in_variable_map':
                data = dict((a, b) for a, _, b in v)
                for key in list(self.variable_maps.get(stack[-1], {}).get(data['variable'], {})):
                    self.execute([e for e in v if e[0] != 'variable'], stack + [key])
            elif k == 'every_owned_location':
                data = dict((a, b) for a, _, b in v)
                for location, owner in list(self.owners.items()):
                    if owner == stack[-1] and self.condition(data.get('limit', []), stack + [location]):
                        self.execute([e for e in v if e[0] != 'limit'], stack + [location])
            elif k == 'trigger_event_silently': self.scheduled.append(v)
            else: super().execute(entries[index:end], stack)
            index = end

    def country(self, name, human=False):
        self.vars[name] = {}; self.lists[name] = {}; self.variable_maps[name] = {}
        if human: self.humans.add(name)

    def manual(self):
        c = self.vars[self.ROOT]
        c.update(eu5ab_manual_month=5, eu5ab_manual_year=1436, eu5ab_manual_computing=1,
                 eu5ab_manual_budget_limit=10000, eu5ab_manual_event_open=1, eu5ab_manual_event_started=1)


class ManualDecisionTests(unittest.TestCase):
    def test_event_property_widgets_have_one_root_after_template_expansion(self):
        gui = manual_decisions.render_event_window()

        def entries(block):
            # GUI template/block declarations omit the script parser's '='.
            block = re.sub(r'\b(?:template|blockoverride|block)\s+("[^"]+"|\w+)\s*\{',
                           r'\1 = {', block)
            return syntax_parse(block)[0][2]

        def expand(nodes):
            result = []
            for key, op, value in nodes:
                if key == 'using':
                    templates = _blocks_for_token(gui, f'template {value} ')
                    self.assertEqual(len(templates), 1, value)
                    result.extend(expand(entries(templates[0])))
                else:
                    result.append((key, op, value))
            return result

        for property_name in ('item', 'scrollwidget'):
            for index, block in enumerate(_blocks_for_token(gui, property_name + ' = ')):
                with self.subTest(property=property_name, index=index):
                    children = expand(entries(block))
                    self.assertEqual(len(children), 1, block)
                    self.assertIsInstance(children[0][2], list, block)

    def test_exhaustive_start_dispatches_over_600_and_waits_for_receipts(self):
        vm = ManualVM()
        c = vm.vars[vm.ROOT]
        c.update(eu5ab_manual_event_open=1, eu5ab_preset_industrial_zone_paused=1)
        # The ordinary initializer resets these fields; the exhaustive dispatcher
        # must populate them itself, including overwriting the previous run date.
        c.update(eu5ab_diag_preliminary_passed=0, eu5ab_diag_deep_scored=0,
                 eu5ab_diag_run_state=0, eu5ab_diag_covered_locations=651,
                 eu5ab_diag_last_run_year=1435, eu5ab_diag_last_run_month=4,
                 eu5ab_diag_last_run_day=22)
        requested = []
        for i in range(651):
            location = f'bound_{i}'
            vm.owners[location] = vm.ROOT
            vm.vars[location] = {'eu5ab_policy_id': 1 if i < 650 else 2}
            vm.lists[location] = {}
        for name in ('eu5ab_clear_engine_candidate_queue', 'eu5ab_clear_scan_continuation',
                     'eu5ab_sync_cmm_settings', 'eu5ab_run_regional_development_policy',
                     'eu5ab_clear_location_worker_state', 'eu5ab_clear_location_candidate_state',
                     'eu5ab_prepare_backfill_dispatch'):
            vm.stubs[name] = lambda: None
        vm.definitions['eu5ab_request_building_capacity'] = parse('save_scope_as = observed_location')
        original = vm.execute
        def observe(entries, stack):
            if len(entries) == 1 and entries[0] == ('save_scope_as', '=', 'observed_location'):
                requested.append(stack[-1])
            else: original(entries, stack)
        vm.execute = observe
        f = generated_fixture()
        for name in ('eu5ab_location_template_not_paused', 'eu5ab_location_template_not_paused_live',
                     'eu5ab_location_template_not_paused_manual'):
            vm.capacity_triggers.update({k: v for k, _, v in parse(_block(f.triggers, name))})
        vm.native['eu5ab_location_need_score'] = 10
        vm.run('eu5ab_manual_begin', vm.ROOT)
        self.assertEqual(len(requested), 650)
        self.assertNotIn('bound_650', requested)
        self.assertEqual(len(vm.lists[vm.ROOT]['eu5ab_worker_pending_locations']), 650)
        self.assertNotIn('eu5ab_manual_ready', c)
        self.assertTrue(c['eu5ab_manual_computing'])
        self.assertEqual(vm.commands, [])
        self.assertEqual([c[f'eu5ab_diag_last_run_{part}'] for part in ('year', 'month', 'day')],
                         [1436, 5, 12])
        self.assertEqual(c['eu5ab_diag_preliminary_passed'], 650)
        self.assertEqual(c['eu5ab_diag_deep_scored'], 650)
        # Complete the real scan reducer after all mocked receipts have arrived.
        vm.lists[vm.ROOT]['eu5ab_worker_pending_locations'].clear()
        vm.definitions.update({k: v for k, _, v in parse(_block(f.effects, 'eu5ab_finish_regional_development_scan'))})
        vm.stubs['eu5ab_hydrate_final_building_diagnostics'] = lambda: None
        vm.stubs['eu5ab_start_engine_candidate_queue'] = lambda: None
        vm.run('eu5ab_finish_regional_development_scan', vm.ROOT)
        self.assertNotEqual(c['eu5ab_diag_run_state'], 4)

    def test_unbound_country_finishes_empty_plan_and_can_close_the_event(self):
        vm = ManualVM()
        f = generated_fixture()
        c = vm.vars[vm.ROOT]
        c.update(eu5ab_diag_preliminary_passed=0, eu5ab_diag_deep_scored=0,
                 eu5ab_diag_run_state=0, eu5ab_diag_covered_locations=0)
        # The batch harness normally seeds an active queue and candidate pool.
        for name in tuple(c):
            if name.startswith('eu5ab_q_'):
                c.pop(name)
        for lists in vm.lists.values():
            lists.clear()
        # Run the real empty-scan -> empty-queue -> manual-finish chain. Native
        # settings/diagnostic refreshes are irrelevant to a country with no binds.
        for name in ('eu5ab_finish_regional_development_scan', 'eu5ab_start_engine_candidate_queue',
                     'eu5ab_finish_engine_candidate_queue'):
            vm.definitions.update({k: v for k, _, v in parse(_block(f.effects, name))})
            vm.stubs.pop(name, None)
        for name in ('eu5ab_clear_engine_candidate_queue', 'eu5ab_clear_scan_continuation',
                     'eu5ab_sync_cmm_settings', 'eu5ab_run_regional_development_policy',
                     'eu5ab_hydrate_final_building_diagnostics', 'eu5ab_sort_candidate_queue',
                     'eu5ab_sort_rgo_candidate_queue', 'eu5ab_refresh_rgo_pending',
                     'eu5ab_recover_pending_rgo_screens', 'eu5ab_dispatch_queue_bridge'):
            vm.stubs[name] = lambda: None
        vm.stubs['eu5ab_request_building_capacity'] = lambda: self.fail('No bound location to sample')
        self.assertFalse(any('eu5ab_policy_id' in values for values in vm.vars.values()))
        event = dict((k, v) for k, _, v in parse(manual_decisions.render_events()))['eu5ab_decisions.2']
        guis = {k: dict((a, b) for a, _, b in v) for k, _, v in parse(manual_decisions.render_guis())}
        vm.execute(next(v for k, _, v in event if k == 'immediate'), [vm.ROOT])
        self.assertTrue(vm.condition(guis['eu5ab_gui_manual_begin']['is_shown'], [vm.ROOT]))
        vm.execute(guis['eu5ab_gui_manual_begin']['effect'], [vm.ROOT])
        self.assertNotIn('eu5ab_manual_computing', c)
        self.assertNotIn('eu5ab_manual_sampling', c)
        self.assertEqual(c.get('eu5ab_manual_count', 0), 0)
        self.assertEqual(c.get('eu5ab_manual_cost', 0), 0)
        self.assertEqual(vm.lists[vm.ROOT].get('eu5ab_manual_plan', []), [])
        self.assertEqual(vm.commands, [])
        self.assertEqual(c['eu5ab_diag_run_state'], 1)
        self.assertEqual(c['eu5ab_diag_preliminary_passed'], 0)
        self.assertEqual(c['eu5ab_diag_deep_scored'], 0)
        self.assertEqual([c[f'eu5ab_diag_last_run_{part}'] for part in ('year', 'month', 'day')],
                         [1436, 5, 12])
        self.assertFalse(vm.condition(guis['eu5ab_gui_manual_waiting']['is_shown'], [vm.ROOT]))
        self.assertTrue(vm.condition(guis['eu5ab_gui_manual_done']['is_valid'], [vm.ROOT]))
        finish = next(v for k, _, v in event if k == 'option'
                      and ('name', '=', 'eu5ab_deep_event_finish') in v)
        vm.execute([e for e in finish if e[0] != 'name'], [vm.ROOT])
        self.assertNotIn('eu5ab_manual_event_open', c)
        self.assertNotIn('eu5ab_manual_event_started', c)

    def test_sampling_visits_all_phases_before_any_approval(self):
        vm = ManualVM(); vm.manual()
        c = vm.vars[vm.ROOT]
        c.update(eu5ab_manual_sampling=1, eu5ab_q_active=1, eu5ab_q_phase=1,
                 eu5ab_monthly_build_quota=0, eu5ab_global_budget_remaining=0)
        vm.lists[vm.ROOT].clear()
        visited = []
        def prepare():
            visited.append(c['eu5ab_q_phase'])
            c['eu5ab_batch_phase'] = c['eu5ab_q_phase']
        vm.stubs['eu5ab_batch_prepare_phase'] = prepare
        vm.stubs['eu5ab_batch_approve'] = lambda: self.fail('Approval during exhaustive sampling')
        vm.run('eu5ab_dispatch_construction_batch', vm.ROOT)
        self.assertEqual(visited, list(range(1, 17)))
        self.assertEqual(vm.commands, [])

    def test_saved_settings_and_template_membership_ignore_live_edits(self):
        vm = ManualVM(); vm.manual()
        c = vm.vars[vm.ROOT]
        c.update(eu5ab_manual_saved_eu5ab_global_min_cash_reserve=700, eu5ab_global_min_cash_reserve=1)
        self.assertEqual(vm.value('eu5ab_manual_value_global_min_cash_reserve', [vm.ROOT]), 700)
        vm.vars['location'].update(eu5ab_manual_location=1, eu5ab_manual_location_owner=vm.ROOT, eu5ab_manual_policy=100,
                                    eu5ab_manual_slot=1, eu5ab_policy_id=3, eu5ab_template_slot=2)
        self.assertEqual(vm.value('eu5ab_manual_policy_value', ['location']), 100)
        self.assertEqual(vm.value('eu5ab_manual_slot_value', ['location']), 1)
        vm.variable_maps[vm.ROOT] = {'eu5ab_manual_saved_eu5ab_tpl_1_building_priorities': {'building': 6}}
        f = generated_fixture()
        for name in ('eu5ab_template_slot_1_building_allowed', 'eu5ab_template_slot_1_building_allowed_live',
                     'eu5ab_template_slot_1_building_allowed_manual'):
            vm.capacity_triggers.update({k: v for k, _, v in parse(_block(f.triggers, name))})
        vm.scopes['eu5ab_candidate_location'] = 'location'
        self.assertTrue(vm.test('eu5ab_template_slot_1_building_allowed', '=', 'yes', ['building']))
        vm.month_number = 6
        self.assertEqual(vm.value('eu5ab_manual_value_global_min_cash_reserve', [vm.ROOT]), 1)

    def test_human_date_and_dispatch_gates(self):
        vm = ManualVM()
        for day in (1, 22):
            vm.day = day
            self.assertTrue(vm.test('eu5ab_manual_allowed', '=', 'yes', [vm.ROOT]))
        for day in (23, 24, 31):
            vm.day = day
            self.assertFalse(vm.test('eu5ab_manual_allowed', '=', 'yes', [vm.ROOT]))
        vm.day = 10
        vm.vars[vm.ROOT]['eu5ab_manual_dispatch_started'] = 1
        self.assertFalse(vm.test('eu5ab_manual_allowed', '=', 'yes', [vm.ROOT]))
        vm.vars[vm.ROOT].pop('eu5ab_manual_dispatch_started')
        vm.humans.clear()
        self.assertFalse(vm.test('eu5ab_manual_allowed', '=', 'yes', [vm.ROOT]))

        decisions = {k: dict((a, b) for a, _, b in v)
                     for k, _, v in parse(manual_decisions.render_decisions())}
        guis = {k: dict((a, b) for a, _, b in v)
                for k, _, v in parse(manual_decisions.render_guis())}
        for index, (name, decision) in enumerate(decisions.items(), 1):
            gui = guis[f'eu5ab_gui_open_{"reset" if index == 1 else "deep"}_confirmation']
            with self.subTest(decision=name):
                self.assertFalse(vm.condition(decision['potential'], [vm.ROOT]))
                self.assertFalse(vm.condition(gui['is_valid'], [vm.ROOT]))
                vm.humans.add(vm.ROOT)
                self.assertTrue(vm.condition(decision['potential'], [vm.ROOT]))
                self.assertTrue(vm.condition(decision['allow'], [vm.ROOT]))
                self.assertEqual(gui['is_valid'], decision['allow'])
                option = dict((a, b) for a, _, b in decision['option'])
                self.assertEqual(gui['effect'], option['effect'])
                before = deepcopy(vm.vars)
                vm.execute(gui['effect'], [vm.ROOT])
                self.assertEqual(vm.scheduled[-1], f'eu5ab_decisions.{index}')
                self.assertEqual(vm.vars, before)  # Opening neither resets nor calculates.
                vm.vars[vm.ROOT]['eu5ab_manual_event_open'] = 1
                self.assertFalse(vm.condition(gui['is_valid'], [vm.ROOT]))
                vm.vars[vm.ROOT].pop('eu5ab_manual_event_open')
                vm.day = 23
                self.assertEqual(vm.condition(gui['is_valid'], [vm.ROOT]), index == 1)
                vm.day = 10
                vm.humans.clear()

    def test_profile_reset_preserves_configuration_and_other_player(self):
        vm = ManualVM()
        vm.country('other', human=True)
        vm.vars['other']['eu5ab_global_budget_spent'] = 123
        vm.owners['foreign'] = 'other'; vm.vars['foreign'] = {'eu5ab_policy_id': 8}; vm.lists['foreign'] = {}
        c = vm.vars[vm.ROOT]
        c.update(eu5ab_tpl_1_exists=1, eu5ab_tpl_1_saved=1, eu5ab_tpl_1_custom_name='Mine',
                 eu5ab_global_budget_spent=500, eu5ab_capacity_sequence=51)
        vm.vars['location'].update(eu5ab_policy_id=100, eu5ab_template_slot=1, eu5ab_failure_cooldown=1)
        vm.variable_maps[vm.ROOT] = {'eu5ab_tpl_1_building_priorities': {'building_type:mill': 7},
                                    'cmm': {'flag:eu5ab_regional_development__enabled': 0, 'flag:other__enabled': 9}}
        vm.lists[vm.ROOT]['cmm_list_items_eu5ab_regional_development__candidate_priority'] = [3, 1, 4, 2]
        vm.lists[vm.ROOT]['eu5ab_profile_countries'] = ['other']
        vm.queues[('location', 'building')] = 1
        for name in ('eu5ab_sync_cmm_settings', 'eu5ab_ensure_annual_budget', 'eu5ab_select_first_player_template'):
            vm.stubs[name] = lambda: None
        other = deepcopy((vm.vars['other'], vm.vars['foreign']))
        vm.run('eu5ab_profile_reset', vm.ROOT)
        self.assertEqual(c['eu5ab_tpl_1_custom_name'], 'Mine')
        self.assertEqual(vm.variable_maps[vm.ROOT]['eu5ab_tpl_1_building_priorities']['building_type:mill'], 7)
        self.assertEqual(vm.lists[vm.ROOT]['cmm_list_items_eu5ab_regional_development__candidate_priority'], [3, 1, 4, 2])
        self.assertNotIn('eu5ab_global_budget_spent', c)
        self.assertNotIn('eu5ab_policy_id', vm.vars['location'])
        self.assertEqual(c['eu5ab_capacity_sequence'], 51)
        self.assertEqual((vm.vars['other'], vm.vars['foreign']), other)
        self.assertEqual(vm.queues[('location', 'building')], 1)
        self.assertEqual(vm.variable_maps[vm.ROOT]['cmm']['flag:other__enabled'], 9)

    def test_transfer_chain_carries_original_configuration_before_reset(self):
        vm = ManualVM()
        vm.country('old'); vm.country('middle')
        vm.vars['old'].update(eu5ab_tpl_1_exists=1, eu5ab_tpl_1_custom_name='Original')
        vm.vars['middle']['eu5ab_tpl_1_custom_name'] = 'Wrong'
        vm.scopes['old_country'] = 'old'
        vm.run('eu5ab_profile_transfer', 'middle')
        vm.scopes['old_country'] = 'middle'
        vm.run('eu5ab_profile_transfer', vm.ROOT)
        for n in ('eu5ab_sync_cmm_settings', 'eu5ab_ensure_annual_budget', 'eu5ab_select_first_player_template'): vm.stubs[n] = lambda: None
        vm.run('eu5ab_profile_reset', vm.ROOT)
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_tpl_1_custom_name'], 'Original')
        self.assertNotIn('eu5ab_tpl_1_custom_name', vm.vars['old'])
        self.assertNotIn('eu5ab_tpl_1_custom_name', vm.vars['middle'])

    def test_association_index_skips_other_humans_and_reassigned_profile(self):
        vm = ManualVM(); vm.country('ai'); vm.country('other', human=True)
        c = vm.vars[vm.ROOT]; c['eu5ab_profile_token'] = 7
        for location, owner, token in [('old_land', 'ai', 7), ('other_land', 'other', 7), ('reused_land', 'ai', 8)]:
            vm.owners[location] = owner
            vm.vars[location] = {'eu5ab_profile_data_token': token, 'eu5ab_policy_id': 1}
            vm.lists[location] = {}
        vm.lists[vm.ROOT]['eu5ab_profile_locations'] = ['old_land', 'other_land', 'reused_land']
        for n in ('eu5ab_sync_cmm_settings', 'eu5ab_ensure_annual_budget', 'eu5ab_select_first_player_template'): vm.stubs[n] = lambda: None
        vm.run('eu5ab_profile_reset', vm.ROOT)
        self.assertNotIn('eu5ab_policy_id', vm.vars['old_land'])
        self.assertEqual(vm.vars['other_land']['eu5ab_policy_id'], 1)
        self.assertEqual(vm.vars['reused_land']['eu5ab_policy_id'], 1)

    def test_rgo_plan_has_no_early_native_order_and_restores_on_23(self):
        class ManualRgoVM(RgoBatchVM, ManualVM): pass
        vm = ManualRgoVM(); vm.manual()
        c = vm.vars[vm.ROOT]
        c.update(eu5ab_manual_month=7, eu5ab_scan_month=7, eu5ab_q_phase=5)
        vm.month_number = 7
        vm.candidate('iron_land', cost=100)
        vm.prepare()
        vm.run('eu5ab_batch_rgo_approve', vm.ROOT); vm.run('eu5ab_batch_rgo_issue', vm.ROOT)
        self.assertEqual(vm.commands, [])
        self.assertEqual(len(vm.lists[vm.ROOT]['eu5ab_manual_plan']), 1)
        vm.lists[vm.ROOT]['eu5ab_manual_locations'] = ['iron_land']
        vm.run('eu5ab_manual_finish', vm.ROOT)
        vm.day = 23; vm.run('eu5ab_manual_execute', vm.ROOT)
        self.assertEqual(len(vm.commands), 1)
        self.assertEqual(vm.commands[0][1:3], ('iron_land', 'rgo'))

    def test_foreign_location_is_not_restored_or_issued_and_next_month_resumes(self):
        vm = ManualVM(); vm.manual(); vm.country('other', human=True)
        c = vm.vars[vm.ROOT]
        c.update(eu5ab_monthly_build_quota=5, eu5ab_constructions_started_this_tick=0)
        vm.add('building_type:one', 20, '100')
        vm.run('eu5ab_batch_approve', vm.ROOT); vm.run('eu5ab_batch_issue', vm.ROOT)
        vm.lists[vm.ROOT]['eu5ab_manual_locations'] = ['location']
        vm.run('eu5ab_manual_finish', vm.ROOT)
        vm.owners['location'] = 'other'
        vm.vars['location']['eu5ab_policy_id'] = 9
        before = deepcopy((vm.vars['location'], vm.variable_maps['location'], vm.lists['location']))
        vm.day = 23; vm.run('eu5ab_manual_execute', vm.ROOT)
        self.assertEqual(vm.commands, [])
        self.assertEqual((vm.vars['location'], vm.variable_maps['location'], vm.lists['location']), before)
        vm.month_number = 6
        vm.stubs['eu5ab_sync_cmm_settings'] = lambda: None
        vm.run('eu5ab_manual_expire', vm.ROOT)
        self.assertFalse(vm.test('eu5ab_manual_month_current', '=', 'yes', [vm.ROOT]))
        self.assertNotIn('eu5ab_manual_executed', c)

    def test_recovery_reissues_incomplete_reads_without_waiting_for_a_day(self):
        vm = ManualVM(); vm.manual()
        c = vm.vars[vm.ROOT]
        c.pop('eu5ab_q_active', None)
        c.update(eu5ab_scan_resume_after_load=1, eu5ab_batch_running=1)
        vm.owners['complete'] = vm.ROOT; vm.vars['complete'] = {'eu5ab_worker_complete': 1}; vm.lists['complete'] = {}
        vm.lists[vm.ROOT]['eu5ab_worker_pending_locations'] = ['location', 'complete']
        vm.vars['location'].pop('eu5ab_worker_complete', None)
        vm.definitions['eu5ab_request_building_capacity'] = parse('set_variable = eu5ab_test_fresh_request')
        vm.stubs['eu5ab_reduce_capacity_batch'] = lambda: None
        vm.run('eu5ab_manual_recover', vm.ROOT)
        self.assertIn('eu5ab_test_fresh_request', vm.vars['location'])
        self.assertNotIn('eu5ab_test_fresh_request', vm.vars['complete'])
        self.assertNotIn('eu5ab_scan_resume_after_load', c)
        self.assertNotIn('eu5ab_batch_running', c)
        self.assertEqual(vm.scheduled, [])
        self.assertNotIn('eu5ab_manual_ready', c)

    def test_new_script_symbols_resolve_and_event_override_keeps_native_other_events(self):
        f = generated_fixture()
        all_scripts = '\n'.join(text for path, text in f.files.items() if path.suffix == '.txt')
        known = set(re.findall(r'(?m)^(eu5ab_\w+)\s*=\s*\{', all_scripts))
        calls = set(re.findall(r'(?<![\w:])(eu5ab_(?:manual|profile)_\w+)\s*=\s*(?:yes|no)\b', all_scripts))
        getters = set(re.findall(r'\beu5ab_manual_value_\w+\b', all_scripts))
        self.assertFalse((calls | getters) - known)
        gui = manual_decisions.render_event_window()
        native = (Path(manual_decisions.__file__).parent / 'assets' / 'eventwindow_1_4.gui').read_text(encoding='utf-8-sig')
        self.assertIn(_blocks_for_token(native, 'template event_option_entry ')[0], gui)
        self.assertIn('template expedition_event_option_entry', gui)
        self.assertIn('name = "omens_event_window"', gui)
        self.assertIn("EventWindow.GetEventKey, 'eu5ab_decisions.2'", gui)

    def test_planning_reserves_in_order_and_allows_final_overspend_without_native_orders(self):
        vm = ManualVM(); vm.manual()
        c = vm.vars[vm.ROOT]
        c.update(eu5ab_manual_budget_limit=150, eu5ab_global_budget_remaining=150,
                 eu5ab_monthly_build_quota=5, eu5ab_constructions_started_this_tick=0)
        first = vm.add('building_type:one', 20, '100')
        second = vm.add('building_type:two', 10, '100')
        vm.run('eu5ab_batch_approve', vm.ROOT)
        vm.run('eu5ab_batch_issue', vm.ROOT)
        self.assertEqual(vm.lists[vm.ROOT]['eu5ab_manual_plan'], [first, second])
        self.assertEqual(c['eu5ab_batch_planned'], 200)
        self.assertEqual(vm.commands, [])
        self.assertEqual(c['eu5ab_global_budget_spent'], 0)

    def test_finish_keeps_plan_and_quote_after_live_data_changes_and_issues_once_on_23(self):
        vm = ManualVM(); vm.manual()
        c = vm.vars[vm.ROOT]
        c.update(eu5ab_monthly_build_quota=5, eu5ab_constructions_started_this_tick=0,
                 eu5ab_diag_run_state=0, eu5ab_diag_preliminary_passed=1, eu5ab_diag_deep_scored=1)
        project = vm.add('building_type:one', 20, '100')
        vm.run('eu5ab_batch_approve', vm.ROOT); vm.run('eu5ab_batch_issue', vm.ROOT)
        vm.lists[vm.ROOT]['eu5ab_manual_locations'] = ['location']
        vm.run('eu5ab_manual_finish', vm.ROOT)
        self.assertTrue(c['eu5ab_manual_ready']); self.assertEqual(c['eu5ab_manual_count'], 1)
        self.assertEqual(c['eu5ab_diag_run_state'], 5)
        self.assertEqual(vm.commands, [])
        vm.variable_maps['location']['eu5ab_quote_cost']['building_type:one'] = 9999
        c['eu5ab_global_enabled'] = 0
        vm.day = 22; vm.run('eu5ab_manual_execute', vm.ROOT)
        self.assertEqual(vm.commands, [])
        vm.day = 23; vm.run('eu5ab_manual_execute', vm.ROOT)
        self.assertEqual([row[0] for row in vm.commands], [project])
        self.assertEqual(vm.variable_maps['location']['eu5ab_quote_cost']['building_type:one'], 100)
        vm.run('eu5ab_manual_execute', vm.ROOT)
        self.assertEqual(len(vm.commands), 1)

    def test_same_event_continue_and_done_are_separate_operations(self):
        f = generated_fixture()
        decisions = parse(manual_decisions.render_decisions())
        self.assertEqual([k for k, _, _ in decisions], ['eu5ab_reset_decision', 'eu5ab_deep_decision'])
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(parse(f.files[root / 'in_game/common/decisions/eu5ab_decisions.txt']), decisions)
        self.assertEqual(parse(f.files[root / 'in_game/common/generic_actions/eu5ab_manual_decisions.txt']), [])
        gui = f.files[next(p for p in f.files if str(p).replace('\\', '/').endswith('/gui/eventwindow.gui'))]
        begin = gui[gui.index('text = "eu5ab_decision_continue"'):gui.index('text = "eu5ab_manual_waiting"')]
        self.assertIn("eu5ab_gui_manual_begin').Execute", begin)
        self.assertNotIn('EventOption.Select', begin)
        self.assertIn("eu5ab_gui_manual_done').IsValid", gui)
        event = dict((k, v) for k, _, v in parse(manual_decisions.render_events()))['eu5ab_decisions.2']
        self.assertEqual(dict((k, v) for k, _, v in event)['interface_lock'], 'yes')
        vm = ManualVM(); vm.manual()
        guis = dict((k, v) for k, _, v in parse(manual_decisions.render_guis()))
        done = dict((k, v) for k, _, v in guis['eu5ab_gui_manual_done'])['is_valid']
        self.assertFalse(vm.condition(done, [vm.ROOT]))
        vm.vars[vm.ROOT]['eu5ab_manual_ready'] = 1
        self.assertTrue(vm.condition(done, [vm.ROOT]))

    def test_native_decision_rows_keep_their_ui_and_route_mod_clicks_directly(self):
        root = Path(__file__).resolve().parents[1]
        native = (Path(manual_decisions.__file__).parent / 'assets' / 'decisions_lateralview_1_4.gui').read_text(encoding='utf-8-sig')
        gui = generated_fixture().files[root / 'in_game/gui/decisions_lateralview.gui']
        token = 'template decision_button_props '
        original, = _blocks_for_token(native, token)
        modified, = _blocks_for_token(gui, token)
        # All native rows, ribbons, progress bars, bells and generic actions survive.
        self.assertEqual(re.sub(r'\s+', ' ', native.replace(original, '')),
                         re.sub(r'\s+', ' ', gui.replace(modified, '')))
        props = syntax_parse(modified.replace(token, 'props = ', 1))[0][2]
        actions = [dict((k, v) for k, _, v in entries)
                   for key, _, entries in props if key == 'action_tooltip']

        def evaluate(node, title):
            if isinstance(node, str):
                return node
            if node[0][0] == 'DecisionItem':
                self.assertEqual([name for name, _ in node],
                                 ['DecisionItem', 'GetDecisionTemplate', 'GetNameWithNoTooltip'])
                return title
            (name, args), = node
            values = [evaluate(arg, title) for arg in args]
            return {'Localize': lambda key: localization[key],
                    'EqualTo_string': lambda a, b: a == b,
                    'Or': lambda a, b: a or b, 'Not': lambda a: not a}[name](*values)

        for language in ('english', 'simp_chinese'):
            localization = {key: json.loads(value) for key, value in re.findall(
                r'^ (\S+): (.+)$', manual_decisions.localization(language), re.M)}
            for kind in ('reset', 'deep', 'ordinary'):
                title = localization.get(f'eu5ab_{kind}_decision.title', 'Another native decision')
                active = [action for action in actions
                          if evaluate(expression(action['visible'].strip('"')), title)]
                with self.subTest(language=language, decision=kind):
                    self.assertEqual(len(active), 1)
                    callback = active[0]['on_action']
                    if kind == 'ordinary':
                        self.assertEqual(callback.strip('"'), '[DecisionItem.OpenWindow]')
                    else:
                        self.assertIn(f"GetScriptedGui('eu5ab_gui_open_{kind}_confirmation').Execute", callback)
                        self.assertEqual(active[0]['click_mode'], 'single')


if __name__ == '__main__': unittest.main()
