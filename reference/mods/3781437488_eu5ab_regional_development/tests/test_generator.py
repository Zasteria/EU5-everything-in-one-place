from pathlib import Path
import json
import re
import tempfile
import unittest

from src.eu5autobuild.generator import (
    ENGLISH_FALLBACK_LANGUAGES,
    PRESET_TEMPLATE_IDS,
    TEMPLATE_NAME_CHOICES,
    _balanced_script,
    _slot_display_name_expr,
    _write_generated_file,
)
from tests._generated import _blocks_for_token, generated_fixture


ROOT = Path(__file__).resolve().parents[1]


def _function_argument_counts(text: str, function: str) -> list[int]:
    token = f"{function}("
    counts: list[int] = []
    offset = 0
    while True:
        start = text.find(token, offset)
        if start < 0:
            return counts
        depth = 1
        commas = 0
        quote: str | None = None
        escaped = False
        index = start + len(token)
        while index < len(text):
            char = text[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif quote is not None:
                if char == quote:
                    quote = None
            elif char in {"'", '"'}:
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    counts.append(commas + 1)
                    break
            elif char == "," and depth == 1:
                commas += 1
            index += 1
        else:
            raise AssertionError(f"{function!r} has an unbalanced call")
        # Resume just after this call's opening token so nested calls are counted too.
        offset = start + len(token)


class GeneratorTests(unittest.TestCase):
    def test_migration_controls_depend_only_on_relocation_master(self):
        from tests._governor_script_vm import GovernorScriptVM, parse
        from tests.test_governor_layout_policy import locations

        gui = self.files[ROOT / "in_game/common/scripted_guis/eu5ab_scripted_guis.txt"]
        for name in ("governor_migration_enabled", "governor_migration_threshold_percent"):
            block = _blocks_for_token(gui, f"eu5ab_regional_development__{name}_on_changed = ")[0]
            predicate = next(body for key, _, body in parse(block)[0][2] if key == "is_shown")
            vm = GovernorScriptVM(locations(1), {}, {}, {}, set(), set(), 0)
            for master in (0, 1):
                for auto in (0, 1):
                    vm.maps[vm.ROOT]["cmm"] = {
                        "flag:eu5ab_regional_development__governor_relocation_enabled": master,
                        "flag:eu5ab_regional_development__governor_migration_enabled": auto,
                    }
                    self.assertEqual(vm.condition(predicate, [vm.ROOT]), bool(master))
        effects = self.files[ROOT / "in_game/common/scripted_effects/eu5ab_scripted_effects.txt"]
        sync = _blocks_for_token(effects, "eu5ab_sync_cmm_settings = ")[0]
        self.assertIn("eu5ab_governor_initialize_relocation_setting = yes", sync)
        self.assertIn("eu5ab_governor_apply_migration_settings = yes", sync)
        self.assertNotIn("eu5ab_governor_disable_migration = yes", sync)

    def test_display_variables_use_guarded_script_values_in_every_language(self):
        from src.eu5autobuild.ui_values import UI_NUMERIC_VARIABLES

        views = "\n".join(content for path, content in self.files.items() if path.suffix in {".gui", ".yml"})
        for variable in UI_NUMERIC_VARIABLES:
            self.assertNotIn(f"GetVariable('{variable}').GetValue", views, variable)
            self.assertIn(f"ScriptValue('{variable}_ui')", views, variable)

    def test_shared_setting_reads_use_initialized_mirrors_including_shift_callbacks(self):
        effects = self.files[ROOT / "in_game/common/scripted_effects/eu5ab_scripted_effects.txt"]
        callbacks = self.files[ROOT / "in_game/common/on_action/eu5ab_on_actions.txt"]
        sync = _blocks_for_token(effects, "\neu5ab_sync_cmm_settings = ")[0]
        initialized = set(re.findall(r"name = (eu5ab_\w+)", sync))
        shift = _blocks_for_token(callbacks, "\neu5ab_on_cmf_callback = ")[0]
        for variable in re.findall(r"value = \{ value = var:(eu5ab_\w+) (?:add|subtract) =", shift):
            self.assertIn(variable, initialized, variable)

    def test_food_failure_counts_keep_numeric_bindings_in_every_language(self):
        from src.eu5autobuild.localization import parse_localization

        for language in ("simp_chinese", "english", *ENGLISH_FALLBACK_LANGUAGES):
            path = ROOT / "in_game" / "localization" / language / f"eu5ab_l_{language}.yml"
            values = parse_localization(self.files[path], language)
            for reason in ("irrigation_need", "granary_need", "storage_pending", "windmill_need"):
                with self.subTest(language=language, reason=reason):
                    self.assertEqual(
                        values[f"eu5ab_diag_fail_{reason}_value"],
                        f"[GetPlayer.MakeScope.ScriptValue('eu5ab_diag_fail_{reason}_ui')|0]",
                    )

    @classmethod
    def setUpClass(cls):
        fixture = generated_fixture()
        cls.policies = fixture.policies
        cls.catalog = fixture.catalog
        cls.building_count = fixture.building_count
        cls.files = fixture.files

    def test_builtin_presets_are_maintained_separately_from_custom_names(self):
        self.assertEqual(
            PRESET_TEMPLATE_IDS,
            tuple(policy.id for policy in self.policies),
        )
        custom_name_ids = {name_id for _, name_id in TEMPLATE_NAME_CHOICES}
        self.assertTrue(set(PRESET_TEMPLATE_IDS).isdisjoint(custom_name_ids))

        scripted_guis = self.files[
            ROOT / "in_game" / "common" / "scripted_guis" / "eu5ab_scripted_guis.txt"
        ]
        for _, name_id in TEMPLATE_NAME_CHOICES:
            rename_action = _blocks_for_token(
                scripted_guis,
                f"eu5ab_gui_slot_1_name_{name_id} = ",
            )[0]
            self.assertNotIn("priority_building_", rename_action)

        effects = self.files[
            ROOT / "in_game" / "common" / "scripted_effects" / "eu5ab_scripted_effects.txt"
        ]
        slot_defaults = _blocks_for_token(
            effects,
            "eu5ab_template_slot_1_ensure_defaults = ",
        )[0]
        self.assertNotIn("key = building_type:city_walls", slot_defaults)
        self.assertIn(
            "name = eu5ab_tpl_1_building_priorities key = building_type:granary value = 10",
            slot_defaults,
        )
        self.assertIn("eu5ab_tpl_1_building_priorities_initialized", slot_defaults)

    def test_expected_files_are_generated(self):
        expected = {
            ".metadata/metadata.json",
            ".metadata/eu5ab_building_upgrades.json",
            ".metadata/eu5ab_construction_demands.json",
            ".metadata/eu5ab_production_recipes.json",
            ".metadata/eu5ab_workforce_model.json",
            ".metadata/eu5ab_governor_connections.json",
            "in_game/common/generic_actions/eu5ab_development_policy_actions.txt",
            "in_game/common/on_action/eu5ab_on_actions.txt",
            "in_game/events/eu5ab_monthly_events.txt",
            "in_game/events/eu5ab_governor_events.txt",
            "in_game/gfx/map/map_modes/eu5ab_template_coverage.txt",
            "in_game/common/scripted_effects/eu5ab_scripted_effects.txt",
            "in_game/common/scripted_effects/eu5ab_governor_effects.txt",
            "in_game/common/script_values/eu5ab_ui_values.txt",
            "in_game/common/scripted_guis/eu5ab_scripted_guis.txt",
            "in_game/common/scripted_guis/eu5ab_governor_scripted_guis.txt",
            "in_game/common/scripted_triggers/eu5ab_scripted_triggers.txt",
            "in_game/common/scripted_triggers/eu5ab_governor_triggers.txt",
            "in_game/common/script_values/eu5ab_script_values.txt",
            "in_game/common/script_values/eu5ab_governor_values.txt",
            "in_game/gui/eu5ab_automation_buildings_window.gui",
            "in_game/gui/eu5ab_engine_queue_window.gui",
            "in_game/gui/eu5ab_governor_recommendation_window.gui",
            "in_game/gui/eu5ab_governor_worker.gui",
            "in_game/gui/eu5ab_template_buildings_window.gui",
            "in_game/gui/eu5ab_template_editor_window.gui",
            "in_game/gui/eu5ab_template_rename_window.gui",
            "in_game/gui/eu5ab_template_rules_window.gui",
            "in_game/gui/eu5ab_template_scope_window.gui",
            "in_game/gui/scripted_widgets/eu5ab_scripted_windows.txt",
            "in_game/localization/simp_chinese/eu5ab_l_simp_chinese.yml",
            "main_menu/localization/simp_chinese/eu5ab_l_simp_chinese.yml",
            "in_game/localization/english/eu5ab_l_english.yml",
            "main_menu/localization/english/eu5ab_l_english.yml",
        }
        expected.update(
            f"{game_layer}/localization/{language}/eu5ab_l_{language}.yml"
            for game_layer in ("in_game", "main_menu")
            for language in ENGLISH_FALLBACK_LANGUAGES
        )
        expected.update(
            f"{layer}/localization/replace/eu5ab_cmm_overrides_l_{language}.yml"
            for layer in ("in_game", "main_menu")
            for language in ("simp_chinese", "english", *ENGLISH_FALLBACK_LANGUAGES)
        )
        actual = {path.relative_to(ROOT).as_posix() for path in self.files}
        self.assertEqual(actual, expected)

    def test_cmm_overrides_are_isolated_and_resolve_to_namespaced_translations(self):
        for layer in ("in_game", "main_menu"):
            for language in ("simp_chinese", "english", *ENGLISH_FALLBACK_LANGUAGES):
                normal = self.files[ROOT / layer / "localization" / language / f"eu5ab_l_{language}.yml"]
                override = self.files[ROOT / layer / "localization/replace" / f"eu5ab_cmm_overrides_l_{language}.yml"]
                for key in ("CMM_NUMERIC_INCREASE_MAX", "CMM_NUMERIC_DECREASE_MIN"):
                    self.assertNotIn(f"\n {key}:", normal)
                    self.assertIn(f"\n EU5AB_{key}:", normal)
                    self.assertIn(f'\n {key}: "$EU5AB_{key}$"', override)

    def test_list_flag_warning_suppression_is_bounded_and_never_mutates_state(self):
        text = self.files[ROOT / "in_game/common/on_action/eu5ab_on_actions.txt"]
        blocks = [b for b in _blocks_for_token(text, "if = ")
                  if "exists = flag:eu5ab_regional_development__candidate_priority_i50_f5" in b]
        block = min(blocks, key=len)
        self.assertIn("always = no", block)
        self.assertNotIn("set_variable", block)
        self.assertNotIn("add_to_variable", block)
        flags = re.findall(r"exists = flag:(\w+)", block)
        self.assertEqual(set(flags), {
            f"eu5ab_regional_development__candidate_priority_i{i}_f{f}"
            for i in range(1, 51) for f in range(1, 6)
        })
        self.assertEqual(len(flags), 250)

    def test_governor_recommendations_do_not_construct_or_remove_buildings(self):
        effects = self.files[ROOT / 'in_game/common/scripted_effects/eu5ab_governor_effects.txt']
        self.assertNotRegex(effects, r'\b(?:construct_building|remove_building|destroy_building)\s*=')

    def test_metadata_declares_cmf_hard_dependency(self):
        payload = json.loads(self.files[ROOT / '.metadata/metadata.json'])
        thumbnail = ROOT / '.metadata' / payload['picture']
        self.assertEqual(thumbnail.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
        dependency = next(item for item in payload['relationships']
                          if item['id'] == 'community_mod_framework')
        self.assertEqual(dependency['rel_type'], 'dependency')
        self.assertEqual(dependency['resource_type'], 'mod')
        self.assertTrue(dependency['version'])

    def test_workforce_metadata_records_vanilla_data_and_no_fake_monthly_rate(self):
        payload = json.loads(
            self.files[ROOT / ".metadata" / "eu5ab_workforce_model.json"]
        )
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["source"]["employment_size_unit_people"], 1000)
        self.assertEqual(payload["source"]["rgo_jobs_per_level"], 1000)
        self.assertEqual(payload["source"]["rgo_primary_pop_type"], "laborers")
        self.assertEqual(payload["source"]["rgo_optional_pop_type"], "slaves")
        self.assertEqual(
            payload["source"]["rgo_optional_pop_type_country_modifier"],
            "allow_rgo_slave_demand",
        )
        self.assertFalse(payload["source"]["monthly_script_value_available"])
        self.assertEqual(payload["source"]["fallback"], "current_available_population")
        buildings = {row["building_id"]: row for row in payload["buildings"]}
        self.assertEqual(buildings["tools_workshop"]["jobs_per_level"], 100)
        self.assertEqual(buildings["tools_workshop"]["pop_types"], ["burghers"])
        paths = {row["source_pop_type"]: row for row in payload["promotion_paths"]}
        self.assertIn("burghers", paths["peasants"]["targets"])

    def test_shared_runtime_settings_live_in_cmm_and_templates_keep_priorities(self):
        effects = self.files[
            ROOT / "in_game" / "common" / "scripted_effects" / "eu5ab_scripted_effects.txt"
        ]
        rules_gui = self.files[
            ROOT / "in_game" / "gui" / "eu5ab_template_rules_window.gui"
        ]
        localization = self.files[
            ROOT / "in_game" / "localization" / "simp_chinese" / "eu5ab_l_simp_chinese.yml"
        ]

        defaults = _blocks_for_token(
            effects, "eu5ab_template_slot_1_ensure_defaults = "
        )[0]
        load = _blocks_for_token(
            effects, "eu5ab_load_template_slot_1_into_editor = "
        )[0]
        commit = _blocks_for_token(
            effects, "eu5ab_commit_template_editor_to_slot_1 = "
        )[0]
        for suffix in (
            "job_fill_deadline_months",
            "native_input_priority",
            "min_cash_reserve",
            "price_min",
            "annual_budget",
            "allow_special_buildings",
            "auto_build_input_sources",
        ):
            self.assertNotIn(f"eu5ab_tpl_1_{suffix}", defaults)
            self.assertNotIn(f"eu5ab_edit_{suffix}", load)
            self.assertNotIn(f"eu5ab_edit_{suffix}", commit)
        self.assertIn("eu5ab_tpl_1_building_priorities", defaults)
        self.assertIn("eu5ab_edit_priority_building_granary", load)
        self.assertIn("name = eu5ab_tpl_1_building_priorities key = building_type:granary", commit)

        self.assertIn("eu5ab_diagnostics_cmm_hint", rules_gui)
        self.assertIn("eu5ab_regional_development_name", localization)
        self.assertIn("eu5ab_regional_development__job_fill_deadline_months_name", localization)

    def test_generated_scripts_have_balanced_braces(self):
        for path, content in self.files.items():
            if path.suffix in {".txt", ".gui"}:
                with self.subTest(path=path):
                    self.assertTrue(_balanced_script(content))

    def test_monthly_hook_uses_eu5_singular_on_action_directory(self):
        singular = ROOT / "in_game" / "common" / "on_action" / "eu5ab_on_actions.txt"
        plural = ROOT / "in_game" / "common" / "on_actions" / "eu5ab_on_actions.txt"
        events = ROOT / "in_game" / "events" / "eu5ab_monthly_events.txt"
        self.assertIn(singular, self.files)
        self.assertNotIn(plural, self.files)
        self.assertIn(events, self.files)
        hook = self.files[singular]
        self.assertIn("monthly_country_pulse", hook)
        self.assertIn("trigger_event_silently = {", hook)
        self.assertIn("id = eu5ab_monthly.1", hook)
        self.assertIn("days = 1", hook)
        self.assertNotIn("eu5ab_run_regional_development_policy = yes", hook)

        event = self.files[events]
        self.assertIn("namespace = eu5ab_monthly", event)
        self.assertIn("type = country_event", event)
        self.assertIn("title = eu5ab_window_title", event)
        self.assertIn("hidden = yes", event)
        self.assertIn("immediate = {", event)
        self.assertEqual(event.count("eu5ab_reset_policy_budgets_if_needed = yes"), 1)
        self.assertEqual(event.count("eu5ab_run_regional_development_policy = yes"), 1)
        self.assertIn("eu5ab_scan_regional_development_bucket = yes", event)
        self.assertIn("eu5ab_finish_regional_development_scan = yes", event)
        # Date boundaries are exercised by test_monthly_schedule_runtime.
        self.assertIn("namespace = eu5ab_queue_watchdog", event)
        self.assertEqual(event.count("save_scope_as = actor"), 5)
        self.assertIn("eu5ab_monthly.3 = {", event)
        self.assertIn("namespace = eu5ab_worker", event)
        self.assertIn("type = location_event", event)
        self.assertIn("eu5ab_run_capacity_worker_once = yes", event)
        first_actor = event.index("save_scope_as = actor")
        first_probe = event.index("eu5ab_run_regional_development_policy = yes")
        self.assertLess(first_actor, first_probe)
        second_actor = event.index("save_scope_as = actor", first_actor + 1)
        finish_probe = event.index("eu5ab_finish_regional_development_scan = yes")
        self.assertLess(second_actor, finish_probe)
        worker_actor = event.rindex("save_scope_as = actor")
        self.assertGreater(worker_actor, finish_probe)

    def test_generates_twenty_template_slots(self):
        combined = "\n".join(self.files.values())
        for slot in range(1, 21):
            with self.subTest(slot=slot):
                self.assertIn(f"eu5ab_template_slot_{slot}_title", combined)
                self.assertIn(f"eu5ab_gui_edit_template_slot_{slot}", combined)
                self.assertIn(f"eu5ab_apply_template_slot_{slot}_to_selected_location", combined)
                self.assertIn(f"eu5ab_apply_template_slot_{slot}_to_selected_province", combined)
                self.assertIn(f"eu5ab_apply_template_slot_{slot}_to_selected_area", combined)
                self.assertIn(f"eu5ab_tpl_{slot}_name_id", combined)
                self.assertIn(f"eu5ab_tpl_{slot}_name_selected", combined)
                self.assertIn(f"eu5ab_template_slot_{slot}_building_allowed", combined)

    def test_template_binding_buttons_use_supported_generic_action_dispatch(self):
        gui = self.files[ROOT / "in_game/gui/eu5ab_automation_buildings_window.gui"]
        actions = self.files[ROOT / "in_game/common/generic_actions/eu5ab_development_policy_actions.txt"]
        self.assertNotIn("action_button = {", gui)
        self.assertNotIn("left_action = {", gui)
        expected = set(re.findall(r"^(eu5ab_apply_\w+_to_selected_\w+) =", actions, re.MULTILINE))
        dispatched = []
        for button in _blocks_for_token(gui, "button_regular = "):
            bindings = _blocks_for_token(button, "scripted_action_tooltip = ")
            if not bindings:
                continue
            self.assertEqual(len(bindings), 1)
            binding = bindings[0]
            self.assertIn("click_type = left", binding)
            self.assertIn("click_mode = single", binding)
            self.assertIn('actor = "[Player]"', binding)
            self.assertIn('visible = "[PdxGuiWidget.IsUberButtonVisible]"', button)
            self.assertIn('enabled = "[PdxGuiWidget.IsUberButtonEnabled]"', button)
            dispatched.append(re.search(r'action_name = "([^"]+)"', binding).group(1))
        self.assertTrue(expected)
        self.assertCountEqual(dispatched, expected)

    def test_rename_dialog_initializes_from_clicked_slot_before_opening(self):
        # A hidden editbox retains its previous text unless its text is bound
        # to the draft that each entry point resets for the clicked template.
        rename_gui = self.files[ROOT / "in_game/gui/eu5ab_template_rename_window.gui"]
        editbox = _blocks_for_token(rename_gui, 'blockoverride "editbox_properties"')[0]
        self.assertIn('text = "[GetVariableSystem.Get(\'eu5ab_template_name_input\')]"', editbox)
        self.assertIn("ontextchanged =", editbox)
        for filename in ("eu5ab_automation_buildings_window.gui", "eu5ab_template_editor_window.gui"):
            gui = self.files[ROOT / "in_game/gui" / filename]
            buttons = [
                block for block in _blocks_for_token(gui, "button_regular = ")
                if 'tooltip = "eu5ab_template_name_click_tooltip"' in block
            ]
            self.assertEqual(len(buttons), 20)
            for slot, button in enumerate(buttons, start=1):
                with self.subTest(filename=filename, slot=slot):
                    display_name = _slot_display_name_expr(slot)
                    initialize = f"GetVariableSystem.Set('eu5ab_template_name_input', {display_name[1:-1]})"
                    show = "GetVariableSystem.Set('eu5ab_template_rename_visible', '1')"
                    self.assertIn(f'raw_text = "{display_name}"', button)
                    self.assertIn(initialize, button)
                    self.assertLess(button.index(initialize), button.index(show))
                    self.assertNotIn("GetVariableSystem.Clear('eu5ab_template_name_input')", button)

    def test_deleting_player_template_clears_its_settings_and_linked_locations(self):
        effects = self.files[
            ROOT / "in_game" / "common" / "scripted_effects" / "eu5ab_scripted_effects.txt"
        ]
        scripted_guis = self.files[
            ROOT / "in_game" / "common" / "scripted_guis" / "eu5ab_scripted_guis.txt"
        ]
        main_gui = self.files[
            ROOT / "in_game" / "gui" / "eu5ab_automation_buildings_window.gui"
        ]

        clear_location = _blocks_for_token(
            effects, "eu5ab_clear_location_policy = "
        )[0]
        for variable in [
            "eu5ab_policy_id",
            "eu5ab_template_slot",
            "eu5ab_policy_decoupled",
        ]:
            self.assertIn(f"remove_variable = {variable}", clear_location)

        delete = _blocks_for_token(
            scripted_guis, "eu5ab_gui_delete_template_slot_1 = "
        )[0]
        self.assertIn("every_owned_location = {", delete)
        self.assertIn("var:eu5ab_template_slot = 1", delete)
        self.assertIn("eu5ab_clear_location_policy = yes", delete)
        self.assertIn("eu5ab_load_blank_template_into_editor = yes", delete)
        self.assertIn(
            "eu5ab_commit_template_editor_to_slot_1_and_refresh_budget = yes",
            delete,
        )
        for variable in ["eu5ab_tpl_1_exists", "eu5ab_tpl_1_saved", "eu5ab_tpl_1_paused"]:
            self.assertIn(f"remove_variable = {variable}", delete)
        self.assertIn("eu5ab_select_first_player_template = yes", delete)

        compatibility_loader = _blocks_for_token(
            effects, "eu5ab_load_new_template_into_editor = "
        )[0]
        self.assertIn(
            "eu5ab_load_recommended_template_into_editor = yes",
            compatibility_loader,
        )
        recommended = _blocks_for_token(
            effects, "eu5ab_load_recommended_template_into_editor = "
        )[0]
        blank = _blocks_for_token(
            effects, "eu5ab_load_blank_template_into_editor = "
        )[0]
        self.assertIn(
            "name = eu5ab_edit_priority_building_granary value = 10",
            recommended,
        )
        self.assertEqual(
            len(re.findall(r"name = eu5ab_edit_priority_building_\w+ value = 0", blank)),
            self.building_count,
        )
        self.assertIn("eu5ab_gui_delete_template_slot_1", main_gui)
        self.assertNotIn("GetVariableSystem.Clear('eu5ab_tpl_1_custom_name')", main_gui)
        self.assertIn("GetVariableSystem.Clear('eu5ab_selected_template_slot')", main_gui)
        self.assertIn("eu5ab_delete_template_button", main_gui)
        self.assertIn('tooltip = "eu5ab_delete_template_tooltip"', main_gui)

    def test_template_footer_confirms_delete_and_toggles_real_pause_state(self):
        main_gui = self.files[
            ROOT / "in_game" / "gui" / "eu5ab_automation_buildings_window.gui"
        ]
        scripted_guis = self.files[
            ROOT / "in_game" / "common" / "scripted_guis" / "eu5ab_scripted_guis.txt"
        ]
        scripted_triggers = self.files[
            ROOT / "in_game" / "common" / "scripted_triggers" / "eu5ab_scripted_triggers.txt"
        ]
        scripted_effects = self.files[
            ROOT / "in_game" / "common" / "scripted_effects" / "eu5ab_scripted_effects.txt"
        ]

        self.assertIn("button_regular_alt_yellow = {", main_gui)
        self.assertIn("button_regular_alt_green = {", main_gui)
        self.assertIn("button_regular_alt_red = {", main_gui)
        self.assertIn("eu5ab_pause_template_button", main_gui)
        self.assertIn("eu5ab_resume_template_button", main_gui)
        self.assertIn("eu5ab_template_paused_badge", main_gui)
        self.assertIn("eu5ab_delete_template_confirm_prompt", main_gui)
        self.assertIn("eu5ab_delete_template_confirm_button", main_gui)
        self.assertIn("eu5ab_delete_template_cancel_button", main_gui)

        open_delete = main_gui.index('text = "eu5ab_delete_template_button"')
        open_delete_block = main_gui[open_delete:open_delete + 500]
        self.assertIn(
            "GetVariableSystem.Set('eu5ab_delete_confirmation_slot', '1')",
            open_delete_block,
        )
        self.assertNotIn("eu5ab_gui_delete_template_slot_1", open_delete_block)

        confirm_delete = main_gui.index('text = "eu5ab_delete_template_confirm_button"')
        confirm_delete_block = main_gui[confirm_delete:confirm_delete + 700]
        self.assertIn("eu5ab_gui_delete_template_slot_1", confirm_delete_block)
        self.assertIn(
            "GetVariableSystem.Clear('eu5ab_delete_confirmation_slot')",
            confirm_delete_block,
        )

        pause = _blocks_for_token(
            scripted_guis, "eu5ab_gui_toggle_template_slot_1_paused = "
        )[0]
        self.assertIn("has_variable = eu5ab_tpl_1_paused", pause)
        self.assertIn("remove_variable = eu5ab_tpl_1_paused", pause)
        self.assertIn("name = eu5ab_tpl_1_paused value = 1", pause)
        preset_pause = _blocks_for_token(
            scripted_guis, "eu5ab_gui_toggle_preset_granary_paused = "
        )[0]
        self.assertIn("has_variable = eu5ab_preset_granary_paused", preset_pause)
        self.assertIn("remove_variable = eu5ab_preset_granary_paused", preset_pause)
        self.assertIn(
            "name = eu5ab_preset_granary_paused value = 1",
            preset_pause,
        )

        slot_one_footer = main_gui[
            main_gui.index("button_regular_alt_yellow = {"):
            main_gui.index('text = "eu5ab_delete_template_button"')
        ]
        self.assertIn(
            "visible = \"[Not(Player.MakeScope.GetVariable('eu5ab_tpl_1_paused').IsSet)]\"",
            slot_one_footer,
        )
        self.assertIn(
            "visible = \"[Player.MakeScope.GetVariable('eu5ab_tpl_1_paused').IsSet]\"",
            slot_one_footer,
        )
        self.assertIn('text = "eu5ab_pause_template_button"', slot_one_footer)
        self.assertIn('text = "eu5ab_resume_template_button"', slot_one_footer)

        not_paused = _blocks_for_token(
            scripted_triggers, "eu5ab_location_template_not_paused = "
        )[0]
        self.assertIn("var:eu5ab_template_slot = 1", not_paused)
        self.assertIn("owner = { has_variable = eu5ab_tpl_1_paused }", not_paused)
        self.assertIn("var:eu5ab_template_slot = 20", not_paused)
        self.assertIn("owner = { has_variable = eu5ab_preset_granary_paused }", not_paused)
        self.assertGreaterEqual(
            scripted_effects.count("eu5ab_location_template_not_paused = yes"),
            41,
        )

    def test_scope_window_can_clear_every_location_shown_for_current_template(self):
        scripted_guis = self.files[
            ROOT / "in_game" / "common" / "scripted_guis" / "eu5ab_scripted_guis.txt"
        ]
        scope_gui = self.files[
            ROOT / "in_game" / "gui" / "eu5ab_template_scope_window.gui"
        ]
        clear_scope = _blocks_for_token(
            scripted_guis, "eu5ab_gui_clear_current_template_scope = "
        )[0]

        self.assertIn("var:eu5ab_scope_location_count > 0", clear_scope)
        self.assertIn("every_owned_location = {", clear_scope)
        self.assertIn("root = { var:eu5ab_scope_view_mode = 1 }", clear_scope)
        self.assertIn("var:eu5ab_template_slot = root.var:eu5ab_scope_view_value", clear_scope)
        self.assertIn("root = { var:eu5ab_scope_view_mode = 2 }", clear_scope)
        self.assertIn("var:eu5ab_policy_id = root.var:eu5ab_scope_view_value", clear_scope)
        self.assertEqual(clear_scope.count("eu5ab_clear_location_policy = yes"), 2)
        self.assertIn("eu5ab_prepare_template_scope_view = yes", clear_scope)
        self.assertIn("eu5ab_gui_clear_current_template_scope", scope_gui)
        self.assertIn("eu5ab_scope_clear_all", scope_gui)
        self.assertIn('tooltip = "eu5ab_scope_clear_all_tt"', scope_gui)

    def test_scripted_windows_register_independent_gui_files(self):
        scripted_windows = self.files[ROOT / "in_game" / "gui" / "scripted_widgets" / "eu5ab_scripted_windows.txt"]
        for relative_path, window in [
            ("eu5ab_automation_buildings_window.gui", "eu5ab_automation_buildings_window"),
            ("eu5ab_template_editor_window.gui", "eu5ab_template_editor_window"),
            ("eu5ab_template_buildings_window.gui", "eu5ab_template_buildings_window"),
            ("eu5ab_template_rules_window.gui", "eu5ab_template_rules_window"),
            ("eu5ab_template_rename_window.gui", "eu5ab_template_rename_window"),
            ("eu5ab_template_scope_window.gui", "eu5ab_template_scope_window"),
        ]:
            self.assertIn(f"gui/{relative_path} = {window}", scripted_windows)
            gui = self.files[ROOT / "in_game" / "gui" / relative_path]
            self.assertRegex(gui, rf'(?m)^window = \{{\n\s*name = "{window}"$')
            self.assertNotIn(f"type {window} = window", gui)

    def test_main_tabs_choose_default_detail(self):
        scripted_gui = self.files[ROOT / "in_game" / "common" / "scripted_guis" / "eu5ab_scripted_guis.txt"]
        effects = self.files[ROOT / "in_game" / "common" / "scripted_effects" / "eu5ab_scripted_effects.txt"]
        on_actions = self.files[ROOT / "in_game" / "common" / "on_action" / "eu5ab_on_actions.txt"]
        main_gui = self.files[ROOT / "in_game" / "gui" / "eu5ab_automation_buildings_window.gui"]
        self.assertIn("eu5ab_gui_open_presets_tab", scripted_gui)
        self.assertIn("set_variable = { name = eu5ab_active_preset_policy value = 1 }", scripted_gui)
        self.assertIn("remove_variable = eu5ab_custom_templates_empty", scripted_gui)
        self.assertIn("eu5ab_gui_open_player_templates", scripted_gui)
        self.assertIn("eu5ab_select_first_player_template = yes", scripted_gui)
        select_first = _blocks_for_token(
            effects, "eu5ab_select_first_player_template = "
        )[0]
        self.assertIn("NOT = { has_variable = eu5ab_active_template_slot }", select_first)
        self.assertIn("set_variable = { name = eu5ab_custom_templates_empty value = 1 }", select_first)
        self.assertIn("set_variable = eu5ab_cmf_window_requested", on_actions)
        callback = on_actions[on_actions.index("eu5ab_on_cmf_callback = {"):]
        self.assertIn("remove_variable = eu5ab_active_preset_policy", callback)
        self.assertIn("eu5ab_select_first_player_template = yes", callback)
        self.assertNotIn(
            "set_variable = { name = eu5ab_active_preset_policy value = 1 }",
            callback.split("# CMM auto-apply", 1)[0],
        )
        self.assertIn("GetVariableSystem.Set('eu5ab_selected_preset', '1')", main_gui)
        self.assertIn("GetVariableSystem.Set('eu5ab_selected_template_slot', '1')", main_gui)
        custom_default = (
            "Or(Not(GetVariableSystem.Exists('eu5ab_main_tab')), "
            "GetVariableSystem.HasValue('eu5ab_main_tab', '2'))"
        )
        flavor_default = (
            "Or(Not(GetVariableSystem.Exists('eu5ab_main_tab')), "
            "GetVariableSystem.HasValue('eu5ab_main_tab', '1'))"
        )
        self.assertIn(custom_default, main_gui)
        self.assertNotIn(flavor_default, main_gui)
        self.assertIn(
            "Or(Not(GetVariableSystem.Exists('eu5ab_selected_template_slot')), "
            "GetVariableSystem.HasValue('eu5ab_selected_template_slot', '1'))",
            main_gui,
        )

    def test_main_panel_selection_and_detail_layout_are_synchronized(self):
        main_gui = self.files[ROOT / "in_game" / "gui" / "eu5ab_automation_buildings_window.gui"]
        preset_selection = "GetVariableSystem.HasValue('eu5ab_selected_preset', '1')"
        template_selection = "GetVariableSystem.HasValue('eu5ab_selected_template_slot', '1')"

        self.assertGreaterEqual(main_gui.count(preset_selection), 2)
        self.assertGreaterEqual(main_gui.count(template_selection), 2)
        self.assertNotIn("GetVariable('eu5ab_active_preset_policy').GetValue", main_gui)
        self.assertNotIn("GetVariable('eu5ab_active_template_slot').GetValue", main_gui)
        self.assertIn(
            'visible = "[Not(Player.MakeScope.GetVariable(\'eu5ab_tpl_1_exists\').IsSet)]"',
            main_gui,
        )
        self.assertIn(
            'visible = "[And(Player.MakeScope.GetVariable(\'eu5ab_tpl_1_exists\').IsSet, Not(Player.MakeScope.GetVariable(\'eu5ab_tpl_2_exists\').IsSet))]"',
            main_gui,
        )
        self.assertIn("GetVariableSystem.Set('eu5ab_selected_template_slot', '20')", main_gui)
        scrollbox_roots = re.findall(
            r'blockoverride "scrollbox_content" \{\s+vbox = \{\s+'
            r'layoutpolicy_horizontal = expanding\s+'
            r'layoutpolicy_vertical = preferred',
            main_gui,
        )
        self.assertEqual(len(scrollbox_roots), 1)
        self.assertRegex(
            main_gui,
            r'blockoverride "scrollbox_content" \{\s+vbox = \{\s+'
            r'layoutpolicy_horizontal = expanding\s+'
            r'layoutpolicy_vertical = fixed',
        )

    def test_main_panel_clicks_use_state_only_after_window_creation(self):
        gui = self.files[ROOT / "in_game" / "gui" / "eu5ab_automation_buildings_window.gui"]
        self.assertNotIn("gui.ClearWidgets eu5ab_automation_buildings_window", gui)
        self.assertNotIn("gui.createwidget gui/eu5ab_automation_buildings_window.gui", gui)
        for gui_id in [
            "eu5ab_gui_open_preset_granary",
            "eu5ab_gui_open_player_templates",
            "eu5ab_gui_open_player_template_slot_1",
            "eu5ab_gui_new_blank_player_template",
            "eu5ab_gui_new_recommended_player_template",
            "eu5ab_gui_open_template_rules_slot_1",
        ]:
            start = gui.index(f"GetScriptedGui('{gui_id}')")
            self.assertNotIn("ExecuteConsoleCommand('gui.", gui[start:start + 500])

    def test_location_target_scopes_are_null_safe(self):
        combined = "\n".join(
            self.files[path]
            for path in [
                ROOT / "in_game" / "common" / "generic_actions" / "eu5ab_development_policy_actions.txt",
                ROOT / "in_game" / "common" / "scripted_effects" / "eu5ab_scripted_effects.txt",
            ]
        )
        self.assertIn("scope:target_location ?=", combined)
        self.assertIn("scope:actor ?=", combined)
        self.assertNotIn("scope:target_location =", combined)

    def test_ui_state_variables_stay_out_of_scripted_guis(self):
        scripted = "\n".join(
            self.files[path]
            for path in [
                ROOT / "in_game" / "common" / "generic_actions" / "eu5ab_development_policy_actions.txt",
                ROOT / "in_game" / "common" / "scripted_effects" / "eu5ab_scripted_effects.txt",
                ROOT / "in_game" / "common" / "scripted_guis" / "eu5ab_scripted_guis.txt",
            ]
        )
        for variable in [
            "eu5ab_main_tab",
            "eu5ab_detail_mode",
            "eu5ab_selected_preset",
            "eu5ab_selected_template_slot",
            "eu5ab_building_filter",
            "eu5ab_location_filter",
            "eu5ab_template_buildings_visible",
            "eu5ab_template_rules_visible",
        ]:
            self.assertNotIn(variable, scripted)

    def test_cmf_action_bar_opens_scripted_widget_without_external_type_overrides(self):
        gui = self.files[ROOT / "in_game" / "gui" / "eu5ab_automation_buildings_window.gui"]
        scripted_windows = self.files[ROOT / "in_game" / "gui" / "scripted_widgets" / "eu5ab_scripted_windows.txt"]
        on_actions = self.files[ROOT / "in_game" / "common" / "on_action" / "eu5ab_on_actions.txt"]
        scripted_guis = self.files[ROOT / "in_game" / "common" / "scripted_guis" / "eu5ab_scripted_guis.txt"]

        self.assertIn("cmf_on_mod_registration", on_actions)
        self.assertIn("cmf_add_action_bar_element = { element = eu5ab_action_bar }", on_actions)
        self.assertIn("cmf_register_scripted_gui = { element = eu5ab_action_bar }", on_actions)
        self.assertIn("cmf_on_country_transfer", on_actions)
        self.assertIn("eu5ab_on_cmf_country_transfer", on_actions)
        transfer = on_actions[on_actions.index("eu5ab_on_cmf_country_transfer = {"):]
        self.assertIn("scope:old_country", transfer)
        self.assertIn("name = cmf_action_bar_active_elements", transfer)
        self.assertIn("target = flag:eu5ab_action_bar", transfer)
        self.assertIn("eu5ab_sync_cmf_action_bar_toggle = yes", transfer)
        self.assertIn("name = cmm_registered_mod_ids", transfer)
        self.assertIn("target = flag:eu5ab_regional_development", transfer)
        self.assertIn("eu5ab_recover_runtime_after_load = yes", transfer)
        effects = self.files[ROOT / "in_game" / "common" / "scripted_effects" / "eu5ab_scripted_effects.txt"]
        self.assertIn("eu5ab_sync_cmf_action_bar_toggle = {", effects)
        self.assertIn("effect = eu5ab_sync_cmf_action_bar_toggle_item", effects)
        self.assertIn("scope:cmm_list_current_item_value = flag:eu5ab_action_bar", effects)
        self.assertIn("cmf_on_callback", on_actions)
        self.assertIn("var:cmf_callback = flag:eu5ab_action_bar", on_actions)
        self.assertIn("set_variable = eu5ab_cmf_window_requested", on_actions)
        self.assertIn("on_game_load_after_lobby_human_country", on_actions)
        self.assertIn("eu5ab_on_cmf_after_load", on_actions)
        self.assertIn("remove_variable = eu5ab_cmf_window_requested", on_actions)
        self.assertIn("eu5ab_action_bar = {", scripted_guis)
        self.assertIn("remove_variable = eu5ab_cmf_window_requested", scripted_guis)
        self.assertIn("Player.MakeScope.GetVariable('eu5ab_cmf_window_requested').IsSet", gui)
        self.assertIn("GetVariableSystem.Clear('eu5ab_window_open')", gui)
        self.assertIn("gui/eu5ab_automation_buildings_window.gui = eu5ab_automation_buildings_window", scripted_windows)
        self.assertNotIn("EU5ABGlorpLeftPanelTypes", gui)
        self.assertNotIn("type button_panel_tab_ideas", gui)
        self.assertNotIn("type button_panel_tab_uniqueevents", gui)
        self.assertNotIn("gui.ClearWidgets", gui)
        self.assertNotIn("gui.createwidget", gui)
        self.assertNotIn("GUI.ClearWidgets ideas_window", gui)

    def test_localization_covers_policy_keys(self):
        localization = self.files[ROOT / "in_game" / "localization" / "simp_chinese" / "eu5ab_l_simp_chinese.yml"]
        english_localization = self.files[
            ROOT / "in_game" / "localization" / "english" / "eu5ab_l_english.yml"
        ]
        main_menu_localization = self.files[ROOT / "main_menu" / "localization" / "simp_chinese" / "eu5ab_l_simp_chinese.yml"]
        self.assertEqual(localization, main_menu_localization)
        keys = set(re.findall(r"^ ([A-Za-z0-9_]+):", localization, flags=re.MULTILINE))
        for policy in self.policies:
            self.assertIn(policy.name_key, keys)
            self.assertIn(policy.description_key, keys)
        for rendered_localization in (localization, english_localization):
            for line in rendered_localization.splitlines()[1:]:
                if line:
                    self.assertRegex(line, r"^ [A-Za-z0-9_]+:")

    def test_supported_languages_merge_reviewed_translations_with_english(self):
        english = self.files[
            ROOT / "in_game" / "localization" / "english" / "eu5ab_l_english.yml"
        ]
        english_keys = re.findall(r"^ ([A-Za-z0-9_]+):", english, flags=re.MULTILINE)
        for language in ENGLISH_FALLBACK_LANGUAGES:
            in_game = self.files[
                ROOT
                / "in_game"
                / "localization"
                / language
                / f"eu5ab_l_{language}.yml"
            ]
            self.assertTrue(in_game.startswith(f"l_{language}:\n"))
            self.assertEqual(
                re.findall(r"^ ([A-Za-z0-9_]+):", in_game, flags=re.MULTILINE),
                english_keys,
            )
            self.assertNotEqual(in_game, english.replace("l_english:", f"l_{language}:", 1))
            for game_layer in ("in_game", "main_menu"):
                with self.subTest(language=language, game_layer=game_layer):
                    localized = self.files[
                        ROOT
                        / game_layer
                        / "localization"
                        / language
                        / f"eu5ab_l_{language}.yml"
                    ]
                    self.assertEqual(localized, in_game)

    def test_generated_localization_uses_bom_and_crlf_on_every_platform(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.yml"
            _write_generated_file(path, 'l_test:\n sample: "Value"\n')
            self.assertEqual(
                path.read_bytes(),
                b'\xef\xbb\xbfl_test:\r\n sample: "Value"\r\n',
            )

    def test_windows_use_eu5_1_3_close_contract_and_player_context(self):
        for filename in [
            "eu5ab_automation_buildings_window.gui",
            "eu5ab_template_editor_window.gui",
            "eu5ab_template_buildings_window.gui",
            "eu5ab_template_rules_window.gui",
            "eu5ab_template_rename_window.gui",
            "eu5ab_template_scope_window.gui",
        ]:
            gui = self.files[ROOT / "in_game" / "gui" / filename]
            with self.subTest(filename=filename):
                self.assertNotIn('blockoverride "close_onclick"', gui)
                self.assertIn('blockoverride "close_on_action"', gui)
                self.assertIn('datacontext = "[GetPlayer]"', gui)
                close_blocks = _blocks_for_token(gui, 'blockoverride "close_on_action"')
                self.assertEqual(len(close_blocks), 1)
                self.assertIn("on_action =", close_blocks[0])
                self.assertNotIn("onclick =", close_blocks[0])
                close_buttons = _blocks_for_token(gui, "button_close_alt")
                self.assertEqual(len(close_buttons), 1)
                self.assertNotIn('input_action = "cancel"', close_buttons[0])
                self.assertNotIn("use_global_input_instance", gui)

    def test_building_rows_are_generated_once_for_active_template(self):
        gui = self.files[ROOT / "in_game" / "gui" / "eu5ab_template_buildings_window.gui"]
        self.assertEqual(
            gui.count("eu5ab_gui_active_priority_dec_"), self.building_count * 3
        )
        self.assertEqual(
            gui.count("eu5ab_gui_active_priority_inc_"), self.building_count * 3
        )
    def test_template_mutations_commit_immediately(self):
        scripted_guis = self.files[
            ROOT / "in_game" / "common" / "scripted_guis" / "eu5ab_scripted_guis.txt"
        ]
        for gui_id in [
            "eu5ab_gui_active_priority_inc_granary",
            "eu5ab_gui_active_priority_dec_granary",
        ]:
            block = _blocks_for_token(scripted_guis, f"{gui_id} = ")[0]
            self.assertIn("eu5ab_commit_active_template_editor = yes", block, gui_id)

    def test_priority_is_zero_to_ten_in_tenths(self):
        effects = self.files[ROOT / "in_game" / "common" / "scripted_effects" / "eu5ab_scripted_effects.txt"]
        triggers = self.files[ROOT / "in_game" / "common" / "scripted_triggers" / "eu5ab_scripted_triggers.txt"]
        values = self.files[ROOT / "in_game" / "common" / "script_values" / "eu5ab_script_values.txt"]
        scripted_guis = self.files[ROOT / "in_game" / "common" / "scripted_guis" / "eu5ab_scripted_guis.txt"]
        self.assertIn("name = eu5ab_tpl_1_building_priorities key = building_type:granary value = 10", effects)
        self.assertNotIn("key = building_type:fruit_orchard value = 0", effects)
        self.assertNotIn("key = building_type:porcelain_manufactory value = 0", effects)
        ensure_block = _blocks_for_token(
            effects, "eu5ab_template_slot_1_ensure_defaults = "
        )[0]
        initialized = "eu5ab_tpl_1_building_priorities_initialized"
        self.assertIn(f"NOT = {{ has_variable = {initialized} }}", ensure_block)
        self.assertIn(
            "NOT = { has_variable_map = eu5ab_tpl_1_building_priorities }",
            ensure_block,
        )
        self.assertLess(
            ensure_block.index(f"NOT = {{ has_variable = {initialized} }}"),
            ensure_block.index("NOT = { has_variable_map = eu5ab_tpl_1_building_priorities }"),
        )
        self.assertIn(f"set_variable = {{ name = {initialized} value = 1 }}", ensure_block)
        commit_block = _blocks_for_token(
            effects, "eu5ab_commit_template_editor_to_slot_1 = "
        )[0]
        self.assertIn(f"set_variable = {{ name = {initialized} value = 1 }}", commit_block)
        self.assertIn("clear_variable_list = eu5ab_active_normal_catalog_template_1", commit_block)
        self.assertIn("remove_variable = eu5ab_active_normal_catalog_template_1_ready", commit_block)
        self.assertLess(
            commit_block.index(f"set_variable = {{ name = {initialized} value = 1 }}"),
            commit_block.index("set_variable = { name = eu5ab_tpl_1_exists value = 1 }"),
        )
        self.assertIn("is_key_in_variable_map = { name = eu5ab_tpl_1_building_priorities target = prev }", triggers)
        self.assertIn('value = "variable_map(eu5ab_tpl_1_building_priorities|prev)"', values)
        self.assertIn("multiply = 50", values)
        self.assertIn("limit = { this = building_type:granary }", values)
        self.assertIn("add = 500", values)
        self.assertIn("add = var:eu5ab_priority_adjust_step", scripted_guis)
        self.assertIn("subtract = var:eu5ab_priority_adjust_step", scripted_guis)
        self.assertIn("value = 0.1", scripted_guis)
        self.assertIn("value = 0.5", scripted_guis)
        self.assertIn("value = 1", scripted_guis)
        copy_block = _blocks_for_token(effects, "eu5ab_copy_template_slot_1_to_slot_2 =")[0]
        self.assertIn("eu5ab_load_template_slot_1_into_editor", copy_block)
        self.assertIn("eu5ab_commit_template_editor_to_slot_2", copy_block)

    def test_scope_cache_and_hierarchy_are_generated(self):
        effects = self.files[ROOT / "in_game" / "common" / "scripted_effects" / "eu5ab_scripted_effects.txt"]
        actions = self.files[ROOT / "in_game" / "common" / "generic_actions" / "eu5ab_development_policy_actions.txt"]
        scripted_guis = self.files[ROOT / "in_game" / "common" / "scripted_guis" / "eu5ab_scripted_guis.txt"]
        editor_gui = self.files[ROOT / "in_game" / "gui" / "eu5ab_automation_buildings_window.gui"]
        scope_gui = self.files[ROOT / "in_game" / "gui" / "eu5ab_template_scope_window.gui"]
        map_mode = self.files[ROOT / "in_game" / "gfx" / "map" / "map_modes" / "eu5ab_template_coverage.txt"]
        localization = self.files[ROOT / "in_game" / "localization" / "simp_chinese" / "eu5ab_l_simp_chinese.yml"]
        english_localization = self.files[
            ROOT / "in_game" / "localization" / "english" / "eu5ab_l_english.yml"
        ]

        self.assertNotIn("eu5ab_recalculate_template_scope_cache", "\n".join(self.files.values()))
        prepare_blocks = _blocks_for_token(effects, "eu5ab_prepare_template_scope_view = ")
        self.assertEqual(len(prepare_blocks), 1)
        prepare = prepare_blocks[0]
        for count_var in [
            "eu5ab_scope_location_count",
            "eu5ab_scope_province_count",
            "eu5ab_scope_area_count",
        ]:
            self.assertIn(count_var, prepare)
        self.assertEqual(prepare.count("every_owned_location = {"), 1)
        self.assertNotIn("every_province = {", prepare)
        self.assertNotIn("every_area = {", prepare)
        self.assertIn("add_to_temporary_list = eu5ab_scope_selected_provinces", prepare)
        self.assertIn("add_to_temporary_list = eu5ab_scope_selected_areas", prepare)
        self.assertIn("is_in_list = eu5ab_scope_selected_provinces", prepare)
        self.assertIn("is_in_list = eu5ab_scope_selected_areas", prepare)
        self.assertEqual(prepare.count("every_in_list = {"), 2)
        self.assertIn("list = eu5ab_scope_selected_provinces", prepare)
        self.assertIn("list = eu5ab_scope_selected_areas", prepare)
        self.assertIn("eu5ab_scope_view_selected", prepare)
        self.assertNotIn("eu5ab_tpl_1_scope_location_count", effects)
        self.assertNotIn("eu5ab_preset_granary_scope_location_count", effects)
        self.assertNotIn("eu5ab_prepare_template_scope_view = yes", actions)

        slot_scope = _blocks_for_token(scripted_guis, "eu5ab_gui_open_template_scope_slot_1 = ")[0]
        self.assertIn("eu5ab_scope_view_mode value = 1", slot_scope)
        self.assertIn("eu5ab_scope_view_value value = 1", slot_scope)
        self.assertIn("eu5ab_prepare_template_scope_view = yes", slot_scope)
        preset_scope = _blocks_for_token(scripted_guis, "eu5ab_gui_open_preset_scope_granary = ")[0]
        self.assertIn("eu5ab_scope_view_mode value = 2", preset_scope)
        self.assertIn("eu5ab_prepare_template_scope_view = yes", preset_scope)
        province_visibility = _blocks_for_token(
            scripted_guis, "eu5ab_gui_active_template_has_locations_in_province = "
        )[0]
        self.assertIn("any_location_in_province", province_visibility)
        self.assertIn("scope = location", province_visibility)
        self.assertNotIn("saved_scopes =", province_visibility)
        self.assertIn("province = {", province_visibility)
        self.assertNotIn("eu5ab_template_slot", province_visibility)
        self.assertNotIn("eu5ab_policy_id", province_visibility)

        self.assertIn('datamodel = "[Player.GetProvinces]"', scope_gui)
        self.assertEqual(scope_gui.count('datamodel = "[Province.GetLocations]"'), 1)
        self.assertIn("Province.GetCapital.GetArea.GetNameWithNoTooltip", scope_gui)
        self.assertNotIn("eu5ab_scope_expanded_province", scope_gui)
        self.assertIn("Province.GetCapital.MakeScope.GetVariable('eu5ab_scope_view_expanded').IsSet", scope_gui)
        self.assertNotIn("Province.MakeScope", scope_gui)
        self.assertIn("eu5ab_gui_expand_scope_province", scope_gui)
        self.assertIn("eu5ab_gui_collapse_scope_province", scope_gui)
        self.assertIn("button_square_plus", scope_gui)
        self.assertIn("button_square_minus", scope_gui)
        self.assertNotIn('raw_text = "+"', scope_gui)
        self.assertNotIn('raw_text = "−"', scope_gui)
        self.assertNotIn("action_tooltip = {", scope_gui)
        self.assertEqual(scope_gui.count("onclick = \"[GetScriptedGui('eu5ab_gui_expand_scope_province')"), 1)
        self.assertEqual(scope_gui.count("onclick = \"[GetScriptedGui('eu5ab_gui_collapse_scope_province')"), 1)
        for gui_id, effect_line in [("expand", "set_variable"), ("collapse", "remove_variable")]:
            block = _blocks_for_token(scripted_guis, f"eu5ab_gui_{gui_id}_scope_province = ")[0]
            self.assertIn("scope = location", block)
            self.assertNotIn("saved_scopes =", block)
            self.assertNotIn("scope:target_province", block)
            self.assertNotIn("\n\t\tprovince = {", block)
            self.assertIn(f"{effect_line} = ", block)
        self.assertIn(
            "GuiScope.SetRoot(Province.GetCapital.MakeScope).End",
            scope_gui,
        )
        self.assertIn("Location.MakeScope.GetVariable('eu5ab_scope_view_selected').IsSet", scope_gui)
        self.assertEqual(scope_gui.count("scrollbox = {"), 1)
        self.assertEqual(scope_gui.count('blockoverride "scrollbox_content"'), 1)
        self.assertNotIn("scrollarea = {", scope_gui)
        self.assertNotIn("scrollwidget = {", scope_gui)
        self.assertNotIn("set_parent_size_to_minimum", scope_gui)
        self.assertIn("layoutpolicy_vertical = expanding", scope_gui)
        self.assertIn("ignoreinvisible = yes", scope_gui)
        self.assertIn("eu5ab_gui_clear_location_template", scope_gui)
        self.assertIn("eu5ab_gui_clear_location_template", scripted_guis)
        clear_scope = _blocks_for_token(
            scripted_guis, "eu5ab_gui_clear_location_template = "
        )[0]
        self.assertIn("scope = country", clear_scope)
        self.assertIn("saved_scopes = { target_location }", clear_scope)
        self.assertIn("scope:target_location ?=", clear_scope)
        self.assertIn("eu5ab_prepare_template_scope_view = yes", clear_scope)
        self.assertNotIn("eu5ab_scope_location_count subtract = 1", clear_scope)
        self.assertNotIn("eu5ab_scope_province_count subtract = 1", clear_scope)
        self.assertNotIn("eu5ab_scope_area_count subtract = 1", clear_scope)
        self.assertNotIn("any_location_in_province", clear_scope)
        self.assertNotIn("any_location_in_area", clear_scope)
        self.assertIn(
            "GuiScope.SetRoot(GetPlayer.MakeScope).AddScope('target_location', Location.MakeScope).End",
            scope_gui,
        )

        for target, parent_scope in [
            ("location", None),
            ("province", "province"),
            ("area", "area"),
        ]:
            action = _blocks_for_token(
                actions,
                f"eu5ab_apply_template_slot_1_to_selected_{target} = ",
            )[0]
            self.assertIn("interaction_source_list = {", action)
            self.assertIn("scope:actor = {", action)
            self.assertIn("every_owned_location = {", action)
            self.assertIn("limit = { NOT = { has_variable = eu5ab_policy_id } }", action)
            self.assertIn("eu5ab_register_location_for_scan = yes", action)
            self.assertNotIn("source = actor", action)
            self.assertNotIn("eu5ab_template_slot_1_ensure_defaults", action)
            self.assertNotIn("eu5ab_template_slot_1_save", action)
            if parent_scope is None:
                self.assertIn("add_to_list = source", action)
            else:
                self.assertIn(f"{parent_scope} = {{", action)
                self.assertIn("is_in_list = source", action)
                parent = _blocks_for_token(action, f"{parent_scope} = ")[0]
                self.assertIn("if = {", parent)
                self.assertNotRegex(parent, rf"^\s*{parent_scope}\s*=\s*\{{\s*limit\s*=",)
                self.assertIn(
                    "owner ?= scope:actor NOT = { has_variable = eu5ab_policy_id }",
                    action,
                )
        for action_id in [
            "eu5ab_decouple_selected_location",
            "eu5ab_clear_selected_location_policy",
        ]:
            action = _blocks_for_token(actions, f"{action_id} = ")[0]
            self.assertIn("limit = { has_variable = eu5ab_policy_id }", action)
        self.assertIn("eu5ab_gui_open_preset_scope_granary", editor_gui)
        self.assertIn("eu5ab_scope_current_summary", localization)
        self.assertNotIn("eu5ab_preset_granary_scope_summary", localization)

        mapmode_lines = [
            line for line in localization.splitlines() if "MAPMODE_EU5AB_TEMPLATE_COVERAGE:" in line
        ]
        self.assertEqual(len(mapmode_lines), 1)
        english_mapmode_lines = [
            line
            for line in english_localization.splitlines()
            if "MAPMODE_EU5AB_TEMPLATE_COVERAGE:" in line
        ]
        self.assertEqual(len(english_mapmode_lines), 1)

        self.assertIn("eu5ab_template_coverage = {", map_mode)
        self.assertIn("category = geography", map_mode)
        self.assertIn("index = 3", map_mode)
        self.assertIn("map_color = {", map_mode)
        self.assertIn("tooltip_key = {", map_mode)
        self.assertIn("owner ?= { is_human = yes }", map_mode)
        self.assertEqual(
            map_mode.count("has_variable = eu5ab_scope_view_mode"),
            4,
        )
        self.assertEqual(
            map_mode.count("has_variable = eu5ab_scope_view_value"),
            4,
        )
        self.assertIn("var:eu5ab_scope_view_mode = 1", map_mode)
        self.assertIn("var:eu5ab_template_slot = owner.var:eu5ab_scope_view_value", map_mode)
        self.assertNotIn("scope:actor", map_mode)
        self.assertNotIn("refresh_colors_on_selection_change", map_mode)
        self.assertIn("define:NMapColors|MAP_COLOR_HIGH", map_mode)
        self.assertIn("define:NMapColors|MAP_COLOR_LOW", map_mode)
        self.assertIn("color_refresh_counters = { Day }", map_mode)
        self.assertIn("mapmode_eu5ab_template_coverage_name", localization)
        self.assertIn("MAPMODE_EU5AB_TEMPLATE_COVERAGE", localization)

    def test_building_filters_ages_and_special_availability_are_generated(self):
        gui = self.files[ROOT / "in_game" / "gui" / "eu5ab_template_buildings_window.gui"]
        scripted_guis = self.files[ROOT / "in_game" / "common" / "scripted_guis" / "eu5ab_scripted_guis.txt"]
        self.assertNotIn("GetVariableSystem.Set('eu5ab_building_filter'", gui)
        open_block = _blocks_for_token(
            scripted_guis, "eu5ab_gui_open_template_buildings_slot_1 = "
        )[0]
        self.assertIn("eu5ab_edit_building_filter value = 0", open_block)
        self.assertIn("eu5ab_edit_building_age value = 0", open_block)
        self.assertIn(
            "clamp_variable = { name = eu5ab_edit_building_filter min = 0 max = 5 }",
            open_block,
        )
        for value in range(6):
            self.assertIn(f"eu5ab_gui_active_building_filter_{value}", gui)
            self.assertIn(f"eu5ab_gui_active_building_filter_{value}", scripted_guis)
        for gui_id, text_key in [
            ("eu5ab_gui_active_building_filter_0", "eu5ab_filter_all"),
            ("eu5ab_gui_active_building_age_0", "eu5ab_age_all"),
        ]:
            blocks = [
                block
                for block in _blocks_for_token(gui, "checkbutton_02_alt = ")
                if gui_id in block
            ]
            self.assertEqual(len(blocks), 1)
            self.assertNotIn("hbox = {", blocks[0])
            self.assertIn('default_format = "#high"', blocks[0])
            self.assertIn("using = Font_Size_Small", blocks[0])
            self.assertIn(f'text = "{text_key}"', blocks[0])
        for age in range(1, 7):
            self.assertIn(f"eu5ab_gui_active_building_age_{age}", gui)
            self.assertIn(f'eu5ab_building_age_{age}', gui)
            self.assertNotIn(f'name = "eu5ab_building_age_group_{age}"', gui)
        self.assertEqual(gui.count('name = "eu5ab_building_age_group_'), 0)
        self.assertIn('visible = "[And(Or(', gui)
        for building_id in ["caravanserai", "funduq"]:
            self.assertIn(f"eu5ab_gui_special_building_available_{building_id}", gui)
            self.assertIn(
                f"GetScriptedGui('eu5ab_gui_special_building_available_{building_id}')"
                ".IsShown(GuiScope.SetRoot(Player.MakeScope)"
                ".AddScope('actor', Player.MakeScope).End)",
                gui,
            )
            self.assertIn(f"eu5ab_gui_special_building_available_{building_id}", scripted_guis)
            self.assertIn(
                f"location_and_owner_can_build = {{ building_type = {building_id} }}",
                scripted_guis,
            )

    def test_priority_buttons_route_default_ctrl_and_shift_steps(self):
        gui = self.files[
            ROOT / "in_game" / "gui" / "eu5ab_template_buildings_window.gui"
        ]
        scripted_guis = self.files[
            ROOT / "in_game" / "common" / "scripted_guis" / "eu5ab_scripted_guis.txt"
        ]
        button = next(
            block
            for block in _blocks_for_token(gui, "button_regular = ")
            if "eu5ab_gui_active_priority_dec_granary" in block
        )
        for modifier, step_id in [
            ("default", "default"),
            ("ctrl", "ctrl"),
            ("shift", "shift"),
        ]:
            self.assertIn(f"click_modifier = {modifier}", button)
            self.assertIn(f"on{modifier} =", button)
            self.assertIn(f"eu5ab_gui_priority_step_{step_id}", button)
        self.assertIn("click_modifiers = {", button)
        self.assertNotIn("\n\t\t\tonclick =", button)

        for step_id, value in [("default", "0.1"), ("ctrl", "0.5"), ("shift", "1")]:
            step = _blocks_for_token(
                scripted_guis,
                f"eu5ab_gui_priority_step_{step_id} = ",
            )[0]
            self.assertIn(f"name = eu5ab_priority_adjust_step value = {value}", step)

        for direction, operation in [("dec", "subtract"), ("inc", "add")]:
            action = _blocks_for_token(
                scripted_guis,
                f"eu5ab_gui_active_priority_{direction}_granary = ",
            )[0]
            self.assertIn(
                f"change_variable = {{ name = eu5ab_edit_priority_building_granary {operation} = var:eu5ab_priority_adjust_step }}",
                action,
            )
            self.assertIn(
                "clamp_variable = { name = eu5ab_edit_priority_building_granary min = 0 max = 10 }",
                action,
            )
            self.assertIn("remove_variable = eu5ab_priority_adjust_step", action)
            self.assertEqual(action.count("eu5ab_commit_active_template_editor = yes"), 1)

    def test_clear_current_list_matches_visible_category_age_and_special_rows(self):
        scripted_guis = self.files[
            ROOT / "in_game" / "common" / "scripted_guis" / "eu5ab_scripted_guis.txt"
        ]
        clear = _blocks_for_token(
            scripted_guis,
            "eu5ab_gui_clear_visible_priorities = ",
        )[0]
        conditions = _blocks_for_token(clear, "\t\tif = ")

        laborer_age_two = next(
            block
            for block in conditions
            if "eu5ab_edit_priority_building_protected_harbor value = 0" in block
        )
        self.assertIn(
            "OR = { var:eu5ab_edit_building_filter = 0 var:eu5ab_edit_building_filter = 2 }",
            laborer_age_two,
        )
        self.assertIn(
            "OR = { var:eu5ab_edit_building_age = 0 var:eu5ab_edit_building_age = 2 }",
            laborer_age_two,
        )
        self.assertNotIn("any_owned_location", laborer_age_two)

        special_age_two = next(
            block
            for block in conditions
            if "eu5ab_edit_priority_building_bajang_ratu value = 0" in block
        )
        self.assertIn(
            "OR = { var:eu5ab_edit_building_filter = 0 var:eu5ab_edit_building_filter = 5 }",
            special_age_two,
        )
        self.assertIn(
            "OR = { var:eu5ab_edit_building_age = 0 var:eu5ab_edit_building_age = 2 }",
            special_age_two,
        )
        self.assertIn("any_owned_location = {", special_age_two)
        self.assertIn(
            "location_and_owner_can_build = { building_type = bajang_ratu }",
            special_age_two,
        )
        self.assertEqual(clear.count("eu5ab_commit_active_template_editor = yes"), 1)
        self.assertGreater(
            clear.rfind("eu5ab_commit_active_template_editor = yes"),
            clear.rfind("value = 0"),
        )

    def test_generated_gui_and_or_calls_are_binary(self):
        gui = "\n".join(
            content
            for path, content in self.files.items()
            if path.suffix == ".gui"
        )
        for function in ["And", "Or"]:
            counts = _function_argument_counts(gui, function)
            self.assertTrue(counts, f"expected at least one {function} call")
            self.assertTrue(
                all(count == 2 for count in counts),
                f"{function} calls must be binary, got {counts}",
            )
        self.assertNotIn("Not([", gui)

    def test_template_price_band_is_explained_and_used(self):
        triggers = self.files[ROOT / "in_game" / "common" / "scripted_triggers" / "eu5ab_scripted_triggers.txt"]
        values = self.files[ROOT / "in_game" / "common" / "script_values" / "eu5ab_script_values.txt"]
        rules_gui = self.files[ROOT / "in_game" / "gui" / "eu5ab_template_rules_window.gui"]
        localization = self.files[ROOT / "in_game" / "localization" / "simp_chinese" / "eu5ab_l_simp_chinese.yml"]
        self.assertIn("eu5ab_output_price_factor > 0", triggers)
        self.assertIn("eu5ab_global_price_min_ratio", values)
        self.assertIn("market_price(goods:", triggers)
        self.assertIn("eu5ab_global_price_max_ratio", values)
        self.assertIn("market_price(goods:", values)
        self.assertNotIn("eu5ab_tpl_1_price_min", values)
        self.assertNotIn("eu5ab_tpl_1_price_max", values)
        granary_score = _blocks_for_token(values, "eu5ab_score_granary = ")[0]
        self.assertIn("add = eu5ab_output_high_price_bonus", granary_score)
        self.assertIn("eu5ab_output_high_price_bonus = {", values)
        self.assertNotIn("add = 180", granary_score)
        self.assertNotIn("template EU5ABRulesHelp_eu5ab_price_section_title", rules_gui)
        self.assertNotIn('text = "eu5ab_price_section_desc"', rules_gui)
        self.assertIn("eu5ab_regional_development__price_min_name", localization)
        self.assertIn("eu5ab_regional_development__price_max_name", localization)
        self.assertNotIn("RGO", localization)
        self.assertNotIn("ROG", localization)

    def test_candidate_diagnostics_store_and_render_each_location_name(self):
        effects = self.files[
            ROOT / "in_game" / "common" / "scripted_effects" / "eu5ab_scripted_effects.txt"
        ]
        rules_gui = self.files[
            ROOT / "in_game" / "gui" / "eu5ab_template_rules_window.gui"
        ]
        localization = self.files[
            ROOT / "in_game" / "localization" / "simp_chinese" / "eu5ab_l_simp_chinese.yml"
        ]
        for rank in range(1, 4):
            self.assertIn(f"name = eu5ab_diag_top_{rank}_location", effects)
            self.assertIn(f"eu5ab_diag_top_{rank}_kind", effects)
            self.assertIn(f"eu5ab_diag_top_{rank}_priority", effects)
            self.assertIn(f'eu5ab_diag_candidate_{rank}_location_value', rules_gui)
            self.assertIn(f'eu5ab_diag_candidate_{rank}_rgo_scores_value', rules_gui)
            self.assertIn(
                f"GetVariable('eu5ab_diag_top_{rank}_location').GetLocation.GetName",
                localization,
            )
        self.assertNotIn("eu5ab_diag_candidate_location_value", rules_gui)
        self.assertNotIn("eu5ab_diag_top_locked", effects)
        self.assertNotIn("eu5ab_diag_top_location_score", effects)
        self.assertNotIn(
            "value = scope:eu5ab_candidate_location.var:eu5ab_worker_top_2_",
            effects,
        )
        self.assertNotRegex(
            effects,
            r"set_variable = \{ name = eu5ab_worker_top_[23]_",
        )
        self.assertIn("eu5ab_candidate_updates_worker_top", effects)
        self.assertIn(
            "name = eu5ab_candidate_diag_priority value = "
            "scope:eu5ab_candidate_location.owner.var:eu5ab_candidate_priority_upgrade",
            effects,
        )
        self.assertIn(
            "name = eu5ab_candidate_diag_priority add = 4",
            effects,
        )
        self.assertIn(
            "var:eu5ab_diag_top_1_priority > { value = "
            "scope:eu5ab_candidate_location.var:eu5ab_worker_top_1_priority }",
            effects,
        )
        self.assertIn(
            "name = eu5ab_diag_top_3_location value = var:eu5ab_diag_top_2_location",
            effects,
        )
        self.assertIn("name = eu5ab_worker_top_1_kind value = 2", effects)
        self.assertIn(
            "name = eu5ab_worker_top_1_labor_jobs value = { "
            "value = eu5ab_rgo_jobs_per_expansion multiply = 1000 }",
            effects,
        )
        self.assertIn(
            "name = eu5ab_worker_top_1_labor_projected value = { "
            "value = eu5ab_rgo_projected_available_workers multiply = 1000 }",
            effects,
        )
        self.assertIn(
            "eu5ab_worker_top_1_priority > { value = "
            "var:eu5ab_rgo_diag_priority }",
            effects,
        )
        self.assertIn("eu5ab_diag_candidate_rgo_value", rules_gui)
        self.assertIn("eu5ab_diag_candidate_empty_value", rules_gui)
        self.assertIn("eu5ab_diag_top_1_kind", rules_gui)
        self.assertIn('text = "eu5ab_diag_candidates_not_scanned_full"', rules_gui)
        self.assertIn("eu5ab_diag_concurrent_limit_state", rules_gui)

    def test_preset_allowlist_overrides_global_zero_priority(self):
        triggers = self.files[
            ROOT / "in_game" / "common" / "scripted_triggers" / "eu5ab_scripted_triggers.txt"
        ]
        values = self.files[
            ROOT / "in_game" / "common" / "script_values" / "eu5ab_script_values.txt"
        ]
        expected_core_buildings = {
            "eu5ab_naval_base_building_allowed": ("shipyard", "naval_base", "dry_dock"),
            "eu5ab_frontier_building_allowed": ("stockade", "castle"),
            "eu5ab_shipbuilding_building_allowed": ("shipyard", "dry_dock"),
            "eu5ab_luxury_goods_building_allowed": (
                "mercury_patio",
                "perfumery",
                "porcelain_manufactory",
            ),
        }
        for trigger_name, building_ids in expected_core_buildings.items():
            block = next(
                block
                for block in _blocks_for_token(triggers, f"{trigger_name} = ")
                if all(f"building_type:{building_id}" in block for building_id in building_ids)
            )
            self.assertTrue(block)

        naval_score = _blocks_for_token(values, "eu5ab_score_naval_base = ")[0]
        self.assertIn("limit = { this = building_type:shipyard }", naval_score)
        self.assertIn("add = 50", naval_score)

    def test_copy_preset_materializes_an_independent_player_template(self):
        effects = self.files[
            ROOT / "in_game" / "common" / "scripted_effects" / "eu5ab_scripted_effects.txt"
        ]
        scripted_guis = self.files[
            ROOT / "in_game" / "common" / "scripted_guis" / "eu5ab_scripted_guis.txt"
        ]
        triggers = self.files[
            ROOT / "in_game" / "common" / "scripted_triggers" / "eu5ab_scripted_triggers.txt"
        ]
        values = self.files[
            ROOT / "in_game" / "common" / "script_values" / "eu5ab_script_values.txt"
        ]
        main_gui = self.files[
            ROOT / "in_game" / "gui" / "eu5ab_automation_buildings_window.gui"
        ]
        rules_gui = self.files[
            ROOT / "in_game" / "gui" / "eu5ab_template_rules_window.gui"
        ]

        loader = next(
            block
            for block in _blocks_for_token(
                effects,
                "eu5ab_load_preset_naval_base_into_editor = ",
            )
            if "eu5ab_edit_priority_building_shipyard" in block
        )
        for expected in [
            "name = eu5ab_edit_name_selected value = 0",
            "name = eu5ab_edit_preset_origin value = 4",
            "name = eu5ab_edit_priority_building_shipyard value = 1",
            "name = eu5ab_edit_priority_building_lumber_mill value = 8",
        ]:
            self.assertIn(expected, loader)
        copy_action = next(
            block
            for block in _blocks_for_token(
                scripted_guis,
                "eu5ab_gui_copy_preset_naval_base_to_player_template = ",
            )
            if "eu5ab_commit_template_editor_to_slot_1_and_refresh_budget" in block
        )
        self.assertIn("eu5ab_load_preset_naval_base_into_editor = yes", copy_action)
        self.assertIn(
            "eu5ab_commit_template_editor_to_slot_1_and_refresh_budget = yes",
            copy_action,
        )
        self.assertIn(
            "GetScriptedGui('eu5ab_gui_copy_preset_naval_base_to_player_template')",
            main_gui,
        )

        # Built-in preset sources are separate from the six player-facing name choices.
        self.assertIn("Localize('eu5ab_policy_naval_base')", main_gui)
        self.assertIn("eu5ab_tpl_1_preset_origin", main_gui)
        self.assertIn("eu5ab_gui_slot_1_name_custom", scripted_guis)
        self.assertNotIn("eu5ab_gui_slot_1_name_naval_base", scripted_guis)

        self.assertNotIn("eu5ab_edit_auto_build_input_sources", rules_gui)
        self.assertNotIn("eu5ab_tpl_1_auto_build_input_sources", triggers)
        self.assertIn("eu5ab_global_auto_build_input_sources", triggers)
        self.assertIn("eu5ab_template_slot_1_building_allowed = yes", triggers)
        self.assertIn("eu5ab_tpl_1_preset_origin", values)

        for gui_id, loader in [
            (
                "eu5ab_gui_new_blank_player_template",
                "eu5ab_load_blank_template_into_editor",
            ),
            (
                "eu5ab_gui_new_recommended_player_template",
                "eu5ab_load_recommended_template_into_editor",
            ),
            ("eu5ab_gui_new_player_template", "eu5ab_load_new_template_into_editor"),
        ]:
            new_template = _blocks_for_token(
                scripted_guis,
                f"{gui_id} = ",
            )[0]
            self.assertLess(
                new_template.index(f"{loader} = yes"),
                new_template.index(
                    "eu5ab_commit_template_editor_to_slot_1_and_refresh_budget = yes"
                ),
            )

    def test_custom_goods_checks_do_not_expand_per_template_slot(self):
        triggers = self.files[ROOT / "in_game" / "common" / "scripted_triggers" / "eu5ab_scripted_triggers.txt"]
        values = self.files[ROOT / "in_game" / "common" / "script_values" / "eu5ab_script_values.txt"]
        self.assertEqual(triggers.count("eu5ab_output_not_oversupplied = {"), 1)
        self.assertEqual(values.count("eu5ab_output_price_factor = {"), 1)
        self.assertNotIn("eu5ab_current_custom_rgo_priority", triggers)
        self.assertNotIn("eu5ab_tpl_1_price_min", triggers)
        self.assertNotIn("eu5ab_tpl_1_rgo_priority", triggers)
        self.assertEqual(values.count("eu5ab_tpl_1_price_min"), 0)
        self.assertEqual(values.count("eu5ab_tpl_1_rgo_priority"), 0)
        self.assertIn("eu5ab_global_price_min_ratio", values)
        self.assertNotIn("eu5ab_global_rgo_priority", values)

    def test_candidate_goods_checks_use_static_catalog_and_rgo_effect_uses_1_3_syntax(self):
        effects = self.files[ROOT / "in_game" / "common" / "scripted_effects" / "eu5ab_scripted_effects.txt"]
        triggers = self.files[ROOT / "in_game" / "common" / "scripted_triggers" / "eu5ab_scripted_triggers.txt"]
        values = self.files[ROOT / "in_game" / "common" / "script_values" / "eu5ab_script_values.txt"]
        for invalid_trigger in (
            "building_goods_input",
            "building_produced_goods",
            "building_potential_profit",
        ):
            self.assertNotIn(invalid_trigger, triggers + values)
        self.assertIn("this = building_type:tools_workshop", triggers)
        self.assertIn("goods_supply_in_market(goods:iron)", triggers)
        self.assertNotIn("construct_rgo_upgrade = yes", effects)
        self.assertIn("construct_rgo_upgrade = { }", effects)

    def test_generated_gui_buttons_have_tooltips(self):
        for path, gui in self.files.items():
            if path.suffix != ".gui":
                continue
            for token in ["button_regular = ", "checkbutton_02_alt = ", "action_button = "]:
                for block in _blocks_for_token(gui, token):
                    with self.subTest(path=path.name, token=token):
                        self.assertTrue(
                            "tooltip =" in block or "tooltipwidget =" in block,
                            f"missing tooltip in {path.name}: {token}",
                        )

if __name__ == "__main__":
    unittest.main()
