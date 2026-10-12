import tempfile
import unittest
from pathlib import Path

from scripts.audit_game_log import audit, script_accesses


class GameLogAuditTests(unittest.TestCase):
    def test_named_queries_and_mutations_do_not_count_as_initialization(self):
        source = '''# set_variable = eu5ab_comment
is_key_in_variable_map = { name = eu5ab_map target = this }
is_target_in_variable_list = { name = eu5ab_list target = this }
change_variable = { name = eu5ab_counter add = 1 }
add_to_variable_map = {
    key = this
    name = eu5ab_written_map
    value = { value = 1 }
}
set_variable = { value = { value = 1 } name = eu5ab_written_scalar }
set_variable = eu5ab_flag
clear_variable_map = eu5ab_legacy_map
'''
        accesses = {(name, kind) for name, kind, _ in script_accesses(source)}
        self.assertEqual(accesses, {
            ('eu5ab_map', 'readers'), ('eu5ab_list', 'readers'),
            ('eu5ab_counter', 'readers'), ('eu5ab_written_map', 'writers'),
            ('eu5ab_written_scalar', 'writers'), ('eu5ab_flag', 'writers'),
            ('eu5ab_legacy_map', 'cleanup'),
        })

    def test_cmm_owned_bounds_and_script_value_consumers_are_classified(self):
        from scripts.audit_game_log import classify

        self.assertEqual(
            classify("cmm_list_field_1_min_eu5ab_regional_development__candidate_priority",
                     "used but is never set", {"references": ["on_action:1"], "writers": ["on_action:1"]}),
            "writer_present_runtime_not_verified",
        )
        self.assertEqual(
            classify("eu5ab_diag_final_quota", "set but is never used",
                     {"references": ["values:1"], "script_readers": ["values:1"]}),
            "script_consumer_present_runtime_not_verified",
        )

    def test_cleanup_is_not_initialization_and_ui_reads_are_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "in_game").mkdir()
            (root / "in_game" / "test.txt").write_text(
                "remove_variable = eu5ab_legacy\n"
                "clear_variable_map = eu5ab_rgo_recent_iron\n"
                "remove_variable = eu5ab_bug\n"
                "if = { limit = { var:eu5ab_bug > 0 } }\n"
                "set_variable = { name = eu5ab_display value = 1 }\n",
                encoding="utf-8",
            )
            (root / "in_game" / "test.gui").write_text(
                "text = GetVariable('eu5ab_display')", encoding="utf-8"
            )
            log = root / "error.log"
            log.write_text(
                "Variable 'eu5ab_legacy' is used but is never set\n"
                "Variable 'eu5ab_rgo_recent_iron' is used but is never set\n"
                "Variable 'eu5ab_bug' is used but is never set\n"
                "Variable 'eu5ab_display' is set but is never used\n"
                "Event target 'cm_country' is used but is never set\n",
                encoding="utf-8",
            )
            report = audit(root, [log])
            states = {row["name"]: row["classification"] for row in report["warnings"]}
            self.assertEqual(states["eu5ab_bug"], "unresolved_read_without_literal_writer")
            self.assertEqual(states["eu5ab_legacy"], "legacy_cleanup_without_reader")
            self.assertEqual(states["eu5ab_rgo_recent_iron"], "legacy_cleanup_without_reader")
            self.assertEqual(states["eu5ab_display"], "consumer_present_runtime_not_verified")
            self.assertEqual(states["cm_country"], "framework_or_other_mod")
