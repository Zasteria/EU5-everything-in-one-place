"""Execute CMF-facing callbacks with injected country settings and list fields.

CMF's public setters are external boundaries, not an emulation of its GUI cache.
"""
from copy import deepcopy
import unittest

from src.eu5autobuild.generator import GLOBAL_RULE_DEFAULTS, _global_setting_var
from tests._generated import generated_fixture, _blocks_for_token
from tests._governor_script_vm import GovernorScriptVM, parse, substitute


PREFIX = 'eu5ab_regional_development__'
BUTTON = 'flag:eu5ab_action_bar'
ACTIVE = 'cmf_action_bar_active_elements'


class CmfVM(GovernorScriptVM):
    def __init__(self):
        super().__init__({}, {}, {}, {}, set(), set(), None)
        fixture = generated_fixture()
        for name in ('eu5ab_on_cmf_callback', 'eu5ab_on_cmf_country_transfer'):
            action = parse(_blocks_for_token(fixture.on_actions, '\n' + name + ' = ')[0])[0][2]
            self.definitions[name] = next(v for k, _, v in action if k == 'effect')
        for name in ('eu5ab_sync_cmm_settings', 'eu5ab_initialize_rgo_settings',
                     'eu5ab_sync_cmf_action_bar_toggle', 'eu5ab_sync_cmf_action_bar_toggle_item'):
            self.definitions.update((k, v) for k, _, v in parse(
                _blocks_for_token(fixture.effects, '\n' + name + ' = ')[0]))
        self.maps[self.ROOT]['cmm'] = {
            'flag:' + PREFIX + key: value for key, value in GLOBAL_RULE_DEFAULTS.items()}
        self.events = []
        self.list_items = ['flag:cmf_core_mod_menu_button', 'flag:another_mod', BUTTON, None]
        for i, value in enumerate(self.list_items, 1):
            if value is not None:
                self.lists[self.ROOT][f'cmf_core__action_bar_buttons_i{i}_value'] = [value]
        # Deliberately move active away from f1: callers must use the field id.
        self.fields = {('cmf_core', 'action_bar_buttons', 'active'): 4}

    def test(self, k, op, v, stack):
        if k == 'exists':
            return self.target(v, stack) is not None
        if k == 'has_variable_list':
            return bool(self.lists[stack[-1]].get(v))
        return super().test(k, op, v, stack)

    def execute(self, entries, stack):
        index = 0
        while index < len(entries):
            k, _, v = entries[index]
            end = index + 1
            if k == 'if':
                while end < len(entries) and entries[end][0] in ('else_if', 'else'):
                    end += 1
            data = dict((a, c) for a, _, c in v) if isinstance(v, list) else {}
            if k == 'cmm_for_each_list_item':
                assert data['setting'] == 'cmf_core__action_bar_buttons'
                for i, value in enumerate(self.list_items, 1):
                    # CMF leaves the previous scope in place for untagged rows.
                    if value is not None:
                        self.scopes['cmm_list_current_item_value'] = value
                    self.execute(substitute(self.definitions[data['effect']],
                                            {'setting': data['setting'], 'i': str(i)}), stack)
            elif k == 'cmm_set_list_field_value':
                assert set(data) == {'mod_id', 'setting_id', 'field_id', 'item', 'value'}
                slot = self.fields[data['mod_id'], data['setting_id'], data['field_id']]
                key = f"flag:{data['mod_id']}__{data['setting_id']}_i{data['item']}_f{slot}"
                self.maps[stack[-1]]['cmm'][key] = self.value(data['value'], stack)
            elif k == 'eu5ab_sync_cmm_settings':
                self.events.append(('sync', stack[-1]))
                self.execute(self.definitions[k], stack)
            elif k in ('eu5ab_governor_apply_migration_settings', 'eu5ab_rebuild_candidate_priority',
                       'eu5ab_refresh_global_budget', 'eu5ab_recover_runtime_after_load'):
                self.events.append((k, stack[-1]))
            else:
                super().execute(entries[index:end], stack)
            index = end


class CmfSettingsRuntimeTests(unittest.TestCase):
    def test_performance_preset_updates_all_values_before_one_settings_sync(self):
        keys = ('parallel_location_scan', 'daily_location_task_limit', 'max_additions_per_run',
                'candidates_per_location', 'actual_profit_candidates_per_location',
                'early_stop_when_candidates_sufficient')
        for preset, expected in ((1, (1, 10, 30, 5, 15, 1)),
                                 (2, (1, 20, 50, 4, 12, 1)),
                                 (3, (1, 30, 0, 3, 10, 1))):
            with self.subTest(preset=preset):
                vm = CmfVM()
                vm.maps[vm.ROOT]['cmm']['flag:' + PREFIX + 'performance_preset'] = preset
                vm.vars[vm.ROOT]['cmf_callback'] = 'flag:' + PREFIX + 'performance_preset'
                vm.call('eu5ab_on_cmf_callback')
                self.assertEqual(tuple(vm.vars[vm.ROOT][_global_setting_var(k)] for k in keys), expected)
                self.assertEqual(vm.events.count(('sync', vm.ROOT)), 1)
                self.assertEqual(vm.maps[vm.ROOT]['cmm']['flag:' + PREFIX + 'performance_preset'], preset)

    def test_budget_step_is_synced_before_budget_refresh_and_manual_tuning_keeps_custom_preset(self):
        vm = CmfVM()
        vm.vars[vm.ROOT].update(cmf_callback='flag:' + PREFIX + 'fixed_annual_budget',
                                eu5ab_global_fixed_annual_budget=5000)
        vm.maps[vm.ROOT]['cmm']['flag:' + PREFIX + 'fixed_annual_budget'] = 999999
        vm.call('eu5ab_on_cmf_callback')
        self.assertEqual(vm.vars[vm.ROOT]['eu5ab_global_fixed_annual_budget'], 6000)
        self.assertLess(vm.events.index(('sync', vm.ROOT)),
                        vm.events.index(('eu5ab_refresh_global_budget', vm.ROOT)))
        vm.vars[vm.ROOT]['cmf_callback'] = 'flag:' + PREFIX + 'daily_location_task_limit'
        vm.call('eu5ab_on_cmf_callback')
        self.assertEqual(vm.maps[vm.ROOT]['cmm']['flag:' + PREFIX + 'performance_preset'], 4)

    def test_country_transfer_syncs_named_field_preserving_other_rows_and_country_data(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                vm = CmfVM()
                vm.vars['old'] = {'eu5ab_template_marker': 7, 'eu5ab_global_budget_spent': 123,
                                  'eu5ab_cmf_window_requested': True, 'eu5ab_scan_resume_after_load': True}
                vm.lists['old'] = {ACTIVE: [BUTTON] if enabled else [],
                                   'cmm_registered_mod_ids': ['flag:eu5ab_regional_development', 'flag:other']}
                vm.lists[vm.ROOT][ACTIVE] = ['flag:another_mod', *([] if enabled else [BUTTON])]
                values = vm.maps[vm.ROOT]['cmm']
                values.update({'flag:cmf_core__action_bar_buttons_i2_f4': 1,
                               'flag:cmf_core__action_bar_buttons_i3_f1': 77})
                before = deepcopy(values)
                vm.scopes['old_country'] = 'old'
                vm.execute(vm.definitions['eu5ab_on_cmf_country_transfer'], [vm.ROOT])
                self.assertEqual(BUTTON in vm.lists[vm.ROOT][ACTIVE], enabled)
                self.assertIn('flag:another_mod', vm.lists[vm.ROOT][ACTIVE])
                self.assertEqual(values, {**before, 'flag:cmf_core__action_bar_buttons_i3_f4': int(enabled)})
                self.assertEqual(vm.vars['old'], {'eu5ab_template_marker': 7, 'eu5ab_global_budget_spent': 123})
                self.assertEqual(vm.lists['old']['cmm_registered_mod_ids'], ['flag:other'])
                self.assertNotIn(BUTTON, vm.lists['old'][ACTIVE])
                self.assertEqual(vm.events, [('eu5ab_recover_runtime_after_load', 'old')])

    def test_settings_registration_matches_callback_inputs(self):
        on_actions = generated_fixture().on_actions
        self.assertIn("cmm_register_bool_setting", on_actions)
        self.assertIn("cmm_register_numeric_setting", on_actions)
        self.assertIn("cmm_register_slider_setting", on_actions)
        self.assertIn("cmm_register_dropdown_setting", on_actions)
        self.assertIn("setting_id = job_fill_deadline_months", on_actions)
        deadline_setting = next(
            block
            for block in _blocks_for_token(
                on_actions, "cmm_register_numeric_setting = "
            )
            if "setting_id = job_fill_deadline_months" in block
        )
        self.assertIn("default_value = 12", deadline_setting)
        self.assertIn("min_value = 0 max_value = 240 step_value = 1", deadline_setting)
        self.assertIn("setting_id = economic_metric", on_actions)
        self.assertIn("eu5ab_sync_cmm_settings = yes", on_actions)
        self.assertIn("eu5ab_refresh_global_budget = yes", on_actions)

        for setting in ('enabled', 'budget_mode', 'min_cash_reserve',
                        'monthly_build_hard_cap', 'candidate_ranking_mode',
                        'allow_rgo', 'native_input_priority'):
            with self.subTest(setting=setting):
                self.assertIn(f'setting_id = {setting}', on_actions)

        presets = next(block for block in _blocks_for_token(on_actions, 'cmm_register_dropdown_setting = ')
                       if 'setting_id = performance_preset' in block)
        self.assertIn('default_index = 3', presets)
        self.assertIn('option_count = 4', presets)


if __name__ == '__main__':
    unittest.main()
