"""Seat-type policy and compile-time bindings for the shared planner templates.

Local identifiers deliberately remain stable for existing saves. Naval work,
published rows, queues and notifications have their own namespace. Binding is
at generation time: no mutable scratch state is shared by the two jobs.
"""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class PlannerType:
    kind: str
    capital_bands: bool
    allow_straits: bool

    def bind(self, text: str) -> str:
        if self.kind == "local":
            return text
        text = text.replace("eu5ab_governor_ensure_planner_schema", "EU5AB_SHARED_SCHEMA_CHECK")
        for old, new in (
            ("eu5ab_fresh_local_governor_slot_available", "eu5ab_fresh_naval_governor_slot_available"),
            ("eu5ab_global_governor_migration_threshold_percent", "eu5ab_global_naval_governor_migration_threshold_percent"),
            ("eu5ab_regional_development__governor_migration_threshold_percent", "eu5ab_regional_development__naval_governor_migration_threshold_percent"),
            ("eu5ab_gui_layout_", "eu5ab_gui_naval_layout_"),
            ("eu5ab_layout_", "eu5ab_naval_layout_"),
            ("eu5ab_gov_", "eu5ab_naval_gov_"),
            ("eu5ab_recalculate_governor_recommendations", "eu5ab_naval_planner_recalculate"),
            ("eu5ab_governor_", "eu5ab_naval_planner_"),
            ("eu5ab_local_", "eu5ab_naval_"),
        ):
            text = text.replace(old, new)
        return text.replace("EU5AB_SHARED_SCHEMA_CHECK", "eu5ab_governor_ensure_planner_schema")

    def bind_ui(self, text: str) -> str:
        if self.kind == "local":
            return text
        for old, new in (
            ("eu5ab_gui_pan_local_governor_", "eu5ab_gui_pan_naval_governor_"),
            ("eu5ab_gui_layout_", "eu5ab_gui_naval_layout_"),
            ("eu5ab_layout_", "eu5ab_naval_layout_"),
            ("eu5ab_governor_local_", "eu5ab_governor_naval_"),
            ("eu5ab_local_", "eu5ab_naval_"),
            ("eu5ab_gov_", "eu5ab_naval_gov_"),
            ("eu5ab_governor_scan_active", "eu5ab_naval_planner_scan_active"),
        ):
            text = text.replace(old, new)
        return text


LOCAL_PLANNER = PlannerType("local", capital_bands=True, allow_straits=False)
NAVAL_PLANNER = PlannerType("naval", capital_bands=False, allow_straits=True)
PLANNER_TYPES = (LOCAL_PLANNER, NAVAL_PLANNER)


def script_definition(text: str, name: str) -> str:
    """Extract a generated, column-zero definition, preserving script operators."""
    match = re.search(rf"^{re.escape(name)} = \{{\n.*?^\}}", text, re.M | re.S)
    if match is None:
        raise ValueError(f"Missing shared planner definition: {name}")
    return match.group()


def render_planner_schema_effects() -> str:
    # The retired unattributed-source flags have no readers. Leave any legacy
    # save values inert; cleanup-only references cause engine unset warnings.
    return '''# Discard incompatible work once, without changing CMM, mute or cooldown values.
eu5ab_governor_ensure_planner_schema = {
    # An unset variable cannot be compared safely, even inside NOT.
    if = {
        limit = { has_variable = eu5ab_planner_schema }
        if = {
            limit = { NOT = { var:eu5ab_planner_schema = 4 } }
            remove_variable = eu5ab_planner_schema
        }
    }
    if = {
        limit = { NOT = { has_variable = eu5ab_planner_schema } }
        if = { limit = { has_variable = eu5ab_governor_scan_active } eu5ab_layout_abort = yes }
        if = { limit = { has_variable = eu5ab_naval_planner_scan_active } eu5ab_naval_layout_abort = yes }
        eu5ab_layout_clear_published_results = yes
        eu5ab_naval_layout_clear_published_results = yes
        eu5ab_governor_clear_country_results = yes
        eu5ab_governor_clear_local_migration = yes
        eu5ab_governor_clear_naval_migration = yes
        eu5ab_governor_clear_naval_results = yes
        cmf_remove_alert = { alert = eu5ab_local_governor_available_alert }
        cmf_remove_alert = { alert = eu5ab_naval_governor_available_alert }
        remove_variable = eu5ab_layout_confirmation_streak
        remove_variable = eu5ab_naval_layout_confirmation_streak
        remove_variable = eu5ab_layout_failed
        remove_variable = eu5ab_naval_layout_failed
        remove_variable = eu5ab_governor_resume_manual
        remove_variable = eu5ab_naval_planner_resume_manual
        remove_variable = eu5ab_governor_manual_run
        remove_variable = eu5ab_naval_planner_manual_run
        clear_variable_list = eu5ab_gov_eval_locations
        clear_variable_list = eu5ab_naval_gov_eval_locations
        every_owned_location = {
            eu5ab_governor_clear_location_cache = yes
            eu5ab_naval_planner_clear_location_cache = yes
            remove_variable = eu5ab_layout_previous_target
            remove_variable = eu5ab_layout_previous_old
            remove_variable = eu5ab_naval_layout_previous_target
            remove_variable = eu5ab_naval_layout_previous_old
        }
        set_variable = eu5ab_governor_dirty
        set_variable = eu5ab_naval_planner_dirty
        set_variable = { name = eu5ab_planner_schema value = 4 }
    }
}
'''
