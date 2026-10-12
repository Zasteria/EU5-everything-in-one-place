"""Structural checks for the planner core; engine integration is tested separately."""
import re
import unittest

from src.eu5autobuild.generator import _balanced_script, render_scripted_windows, GLOBAL_RULE_DEFAULTS
from src.eu5autobuild.governor_generator import render_governor_effects, render_governor_script_values, render_governor_scripted_guis, render_governor_gui, render_governor_triggers
from src.eu5autobuild.governor_layout_generator import render_layout_effects
from src.eu5autobuild.governor_planner import NAVAL_PLANNER, script_definition
from src.eu5autobuild.governor_layout_ui import (
    render_layout_scripted_guis, render_layout_worker_gui, LAYOUT_SIMP_CHINESE, LAYOUT_ENGLISH,
)
from tests._generated import _blocks_for_token


class LayoutGeneratorTests(unittest.TestCase):
    def test_filtered_land_paths_use_dedicated_edge_value_and_naval_keeps_straits(self):
        values = render_governor_script_values()
        local_value = script_definition(values, "eu5ab_governor_known_land_edge_prediction")
        general_value = script_definition(values, "eu5ab_governor_land_edge_prediction")
        self.assertNotIn("is_strait_connection_to", local_value)
        self.assertIn("is_strait_connection_to", general_value)

        effects = render_governor_effects()
        for prefix in ("eu5ab_governor", "eu5ab_naval_planner"):
            queue = script_definition(effects, prefix + "_queue_relax_one")
            self.assertIn("eval_kind = 2", queue)
            self.assertIn(prefix + "_land_edge_prediction", queue)
            self.assertIn(prefix + "_known_land_edge_prediction", queue)
            self.assertIn("is_strait_connection_to", queue)

        local_layout = script_definition(render_layout_effects(), "eu5ab_layout_relax_one")
        naval_layout = script_definition(render_layout_effects(NAVAL_PLANNER), "eu5ab_naval_layout_relax_one")
        self.assertIn("NOT = { eu5ab_is_strait_connection_to", local_layout)
        self.assertIn("eu5ab_governor_actual_land_edge_prediction", local_layout)
        self.assertNotIn("NOT = { eu5ab_is_strait_connection_to", naval_layout)
        self.assertIn("eu5ab_naval_planner_actual_land_edge_prediction", naval_layout)

    def test_complete_rows_are_validated_before_confirmation_or_scores(self):
        effects = render_layout_effects()
        rows = _blocks_for_token(effects, "\neu5ab_layout_publish_rows = ")[0]
        ordered = _blocks_for_token(rows, "ordered_owned_location = ")[0]
        self.assertIn("max = var:eu5ab_layout_seats", ordered)
        publish = _blocks_for_token(effects, "\neu5ab_layout_publish = ")[0]
        validation = publish.index("eu5ab_layout_validate_rows = yes")
        self.assertLess(publish.index("eu5ab_layout_publish_rows = yes"), validation)
        self.assertLess(validation, publish.index("eu5ab_layout_confirm = yes"))
        self.assertLess(validation, publish.index("name = eu5ab_layout_result_before"))
        invalid = next(block for block in _blocks_for_token(publish, "if = ")
                       if "limit = { has_variable = eu5ab_layout_invalid_rows }" in block)
        self.assertIn("eu5ab_layout_clear_published_results = yes", invalid)
        self.assertIn("eu5ab_layout_abort = yes", invalid)

    def test_retained_rows_do_not_show_migration_arrows_or_migration_note(self):
        blocks = _blocks_for_token(render_governor_gui(), "text_multi = ")
        for rank in (1, 2, 3):
            retained = f"GetPlayer.MakeScope.GetVariable('eu5ab_layout_view_{rank}_retained').IsSet"
            moving = next(b for b in blocks if f'text = "eu5ab_layout_row_{rank}"' in b)
            keeping = next(b for b in blocks if f'text = "eu5ab_layout_row_{rank}_retained"' in b)
            self.assertIn(f'visible = "[Not({retained})]"', moving)
            self.assertIn(f'visible = "[{retained}]"', keeping)
            note = next(b for b in blocks if 'text = "eu5ab_layout_row_note"' in b
                        and retained in b)
            self.assertIn(f'visible = "[Not({retained})]"', note)
            for catalog in (LAYOUT_SIMP_CHINESE, LAYOUT_ENGLISH):
                self.assertNotIn("→", catalog[f"eu5ab_layout_row_{rank}_retained"])
                self.assertIn("→", catalog[f"eu5ab_layout_row_{rank}"])

    def test_dirty_publication_uses_shared_pipeline_without_manual_event_side_effects(self):
        publish = _blocks_for_token(render_layout_effects(), "\neu5ab_layout_publish = ")[0]
        dirty = next(block for block in _blocks_for_token(publish, "else_if = ")
                     if "limit = { has_variable = eu5ab_governor_dirty }" in block)
        self.assertIn("eu5ab_recalculate_governor_recommendations = yes", dirty)
        for forbidden in ("eu5ab_layout_begin = yes", "eu5ab_layout_abort = yes",
                          "eu5ab_governor_run_recalculation_now = yes",
                          "eu5ab_governor_manual_recalculation = yes",
                          "trigger_event", "skip_next_scheduled_event"):
            self.assertNotIn(forbidden, dirty)

    def test_candidate_items_use_fixed_widgets_and_valid_empty_text_alignment(self):
        gui = render_governor_gui()
        for kind in ("local", "naval"):
            for rank in (1, 2, 3):
                card = next(block for block in _blocks_for_token(gui, "widget = ")
                            if f'name = "eu5ab_{kind}_candidate_{rank}_card"' in block)
                item = _blocks_for_token(card, "item = ")[0]
                self.assertRegex(item, r"item = \{\s+widget = \{")
                self.assertNotIn("container = {", item)
                self.assertIn('datacontext = "[Scope.GetLocation]"', item)
                self.assertIn("vbox = {", item)
        self.assertNotIn("align = center|top", gui)

    def test_refresh_can_recover_active_scan_and_initial_candidates_exclude_built_seats(self):
        refresh = _blocks_for_token(render_governor_scripted_guis(), "eu5ab_gui_governor_refresh_now = ")[0]
        self.assertNotIn("has_variable = eu5ab_governor_scan_active", refresh)
        trigger = _blocks_for_token(render_governor_triggers(), "eu5ab_local_governor_candidate = ")[0]
        self.assertIn("NOT = { has_building = building_type:local_governor }", trigger)
        gui = render_governor_gui()
        for key in ("eu5ab_governor_refresh_progress", "eu5ab_governor_refresh_failure"):
            block = next(b for b in _blocks_for_token(gui, "text_multi = ") if f'text = "{key}"' in b)
            self.assertIn("layoutpolicy_horizontal = expanding", block)

    def test_migration_defaults_off_and_naval_full_slot_work_is_gated(self):
        self.assertEqual(GLOBAL_RULE_DEFAULTS["governor_migration_enabled"], 0)
        self.assertEqual(GLOBAL_RULE_DEFAULTS["governor_relocation_enabled"], 1)
        self.assertEqual(GLOBAL_RULE_DEFAULTS["governor_recommendations_enabled"], 1)
        effects = render_governor_effects()
        pipeline = _blocks_for_token(effects, "\neu5ab_naval_planner_refresh_tick = ")[0]
        self.assertIn("var:eu5ab_global_governor_migration_enabled > 0", pipeline)
        self.assertIn("var:eu5ab_global_governor_relocation_enabled > 0", pipeline)
        self.assertIn("has_variable = eu5ab_naval_planner_manual_run", pipeline)
        commit = script_definition(effects, "eu5ab_naval_planner_refresh_commit")
        self.assertIn("has_variable = eu5ab_naval_gov_refresh_need_layout", commit)
        self.assertIn("eu5ab_naval_layout_begin = yes", commit)

    def test_effects_are_closed_and_reference_defined_planner_effects(self):
        text = render_layout_effects()
        self.assertTrue(_balanced_script(text))
        definitions = re.findall(r"^(eu5ab_\w+) = \{", text, re.M)
        self.assertEqual(len(definitions), len(set(definitions)))
        available = set(definitions) | set(re.findall(
            r"^(eu5ab_\w+) = \{", render_governor_effects(), re.M))
        for called in re.findall(r"\b(eu5ab_\w+) = yes", text):
            if called.endswith("_candidate"):
                continue  # separately generated structural trigger
            self.assertIn(called, available)
        self.assertNotRegex(text, r"\b(?:construct_building|remove_building|destroy_building)\b")

    def test_wave_is_budgeted_without_depth_cutoff_and_preserves_partial_work(self):
        text = render_layout_effects()
        tick = _blocks_for_token(text, "\neu5ab_layout_tick = ")[0]
        relax = _blocks_for_token(text, "\neu5ab_layout_relax_one = ")[0]
        self.assertIn("count = 64", tick)
        self.assertIn("max = 64", tick)
        self.assertNotIn("depth", relax)
        self.assertIn("var:eu5ab_layout_wave_work >= var:eu5ab_layout_wave_budget", tick)
        abort = _blocks_for_token(text, "\neu5ab_layout_abort = ")[0]
        self.assertNotIn("eu5ab_layout_publish_rows = yes", abort)
        self.assertNotIn("remove_variable = eu5ab_layout_row_to", abort)
        self.assertIn("remove_variable = eu5ab_layout_confirmation_streak", abort)

    def test_no_live_snapshot_shortlist_or_partial_row_publish(self):
        text = render_layout_effects()
        self.assertNotIn("max = 8", text)
        self.assertNotIn("subtract = proximity", text)
        choose = _blocks_for_token(text, "\neu5ab_layout_choose = ")[0]
        self.assertIn("eu5ab_layout_band_order", choose)
        self.assertIn("eu5ab_layout_scored_round", choose)
        self.assertIn("eu5ab_layout_last_footprint", choose)
        self.assertNotIn("eu5ab_layout_row_to", choose)

    def test_worker_runs_independently_and_paging_refreshes_rows(self):
        self.assertIn("gui/eu5ab_governor_worker.gui = eu5ab_governor_worker",
                      render_scripted_windows())
        worker = render_layout_worker_gui()
        self.assertIn("eu5ab_gui_layout_tick", worker)
        self.assertNotIn("governor_window_open", worker)
        self.assertIn('visible = "[GetPlayer.Exists]"', worker)
        # Request gating belongs to the repeated sender, never the persistent timer.
        self.assertNotRegex(worker, r'visible = "[^"\n]*\.IsShown\(')
        self.assertNotRegex(worker, r'visible = "[^"\n]*scan_active')
        self.assertIn("EqualTo_CFixedPoint", worker)
        guis = render_layout_scripted_guis()
        for direction in ("previous", "next"):
            page = _blocks_for_token(guis, f"\neu5ab_gui_layout_{direction} = ")[0]
            self.assertIn("eu5ab_layout_refresh_page = yes", page)
        monthly = _blocks_for_token(render_governor_effects(),
                                    "\neu5ab_governor_monthly_pulse = ")[0]
        self.assertIn("remove_variable = eu5ab_layout_confirmation_streak", monthly)
        self.assertIn("eu5ab_layout_schedule_watchdog = yes", monthly)
        self.assertIn("NOT = { has_variable = eu5ab_governor_scan_active }", monthly)

if __name__ == "__main__":
    unittest.main()
