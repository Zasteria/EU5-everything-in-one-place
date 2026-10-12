"""Persistent template coverage, independent of monthly scan progress."""


def render_effects() -> str:
    return '''# Count all owned template bindings, including paused and cooling locations.
# Old saves contain a partial scan counter under the same diagnostic name.
# Recount once without changing scan buckets, cursors or construction work.
eu5ab_ensure_template_coverage = {
    if = { limit = { NOT = { has_variable = eu5ab_template_coverage_initialized } }
        save_scope_as = eu5ab_coverage_country
        set_variable = { name = eu5ab_diag_covered_locations value = 0 }
        every_owned_location = {
            # Owner changes can arrive in batches before their callbacks run.
            # Release a previous owner's count before adopting its location.
            eu5ab_remove_location_template_coverage = yes
            if = { limit = { has_variable = eu5ab_policy_id }
                set_variable = { name = eu5ab_template_coverage_owner value = scope:eu5ab_coverage_country }
                scope:eu5ab_coverage_country = { change_variable = { name = eu5ab_diag_covered_locations add = 1 } }
            }
        }
        set_variable = eu5ab_template_coverage_initialized
    }
}

# A location contributes once, even when its template is reapplied or replaced.
eu5ab_sync_location_template_coverage = {
    if = { limit = { has_variable = eu5ab_policy_id }
        save_scope_as = eu5ab_coverage_location
        owner ?= {
            eu5ab_ensure_template_coverage = yes
            save_scope_as = eu5ab_coverage_country
            scope:eu5ab_coverage_location = {
                if = { limit = { NOT = { AND = {
                    has_variable = eu5ab_template_coverage_owner
                    var:eu5ab_template_coverage_owner = scope:eu5ab_coverage_country
                } } }
                    eu5ab_remove_location_template_coverage = yes
                    scope:eu5ab_coverage_country = { change_variable = { name = eu5ab_diag_covered_locations add = 1 } }
                    set_variable = { name = eu5ab_template_coverage_owner value = scope:eu5ab_coverage_country }
                }
            }
        }
    }
}

# The stored country remains the contributor after a native ownership change.
eu5ab_remove_location_template_coverage = {
    if = { limit = { has_variable = eu5ab_template_coverage_owner }
        var:eu5ab_template_coverage_owner ?= {
            if = { limit = { has_variable = eu5ab_template_coverage_initialized }
                change_variable = { name = eu5ab_diag_covered_locations subtract = 1 }
            }
        }
        remove_variable = eu5ab_template_coverage_owner
    }
}
'''
