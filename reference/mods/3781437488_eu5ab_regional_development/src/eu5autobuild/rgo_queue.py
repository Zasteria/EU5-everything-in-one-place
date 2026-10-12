"""Native RGO counts for worker snapshots and registered pending projects.

Nonempty civil queues need an exact GUI reading. Empty queues prove zero in
script. Unknown readings never become zero or release a pending project.
Requests enumerate only registered locations, never every owned location.
"""

from .gui_integer import nonnegative_int32

GUI_SCOPES = 'eu5ab_engine_rgo_count'


def gui_arguments() -> str:
    return (".AddScope('eu5ab_engine_rgo_count', MakeScopeValue("
            + nonnegative_int32('Location.GetMaxRGOWorkersUnderConstruction') + '))')


def render_values() -> str:
    return '''
# Zero variables may disappear in EU5; readiness is independent of the value.
eu5ab_rgo_queue_count_value = { value = 0
    if = { limit = { has_variable = eu5ab_rgo_queue_count } add = var:eu5ab_rgo_queue_count }
}
eu5ab_rgo_queue_level_value = { value = 0
    if = { limit = { has_variable = eu5ab_rgo_queue_level } add = var:eu5ab_rgo_queue_level }
}
# Timed-variable days accepts a named script value, not a direct var: target.
eu5ab_rgo_pending_wait_days = {
    value = var:eu5ab_rgo_pending_build_days
}
eu5ab_rgos_under_construction = {
    value = -1
    if = { limit = { num_civil_constructions = 0 } value = 0 }
    else_if = { limit = { eu5ab_rgo_queue_current = yes } value = eu5ab_rgo_queue_count_value }
}
# Workforce reservations may use a conservative bound while awaiting a read.
# This bound is never used for project identity, cancellation or output release.
eu5ab_rgo_queued_jobs = {
    value = eu5ab_rgos_under_construction
    if = { limit = { eu5ab_rgos_under_construction < 0 } value = num_civil_constructions }
    multiply = eu5ab_rgo_jobs_per_expansion
}
'''


def render_triggers() -> str:
    return '''
eu5ab_rgo_queue_current = {
    has_variable = eu5ab_rgo_queue_ready exists = var:eu5ab_rgo_queue_owner
    has_variable = eu5ab_rgo_queue_day has_variable = eu5ab_rgo_queue_civil
    trigger_if = { limit = {
        has_variable = eu5ab_rgo_queue_ready exists = var:eu5ab_rgo_queue_owner
        has_variable = eu5ab_rgo_queue_day has_variable = eu5ab_rgo_queue_civil
    }
        owner = var:eu5ab_rgo_queue_owner
        var:eu5ab_rgo_queue_day = eu5ab_pl_today
        var:eu5ab_rgo_queue_civil = num_civil_constructions
        eu5ab_rgo_queue_level_value = rgo_level
    }
}
eu5ab_rgo_queue_request_current = {
    exists = var:eu5ab_rgo_queue_request_owner
    has_variable = eu5ab_rgo_queue_request_day has_variable_list = eu5ab_rgo_queue_tickets
    trigger_if = { limit = { exists = var:eu5ab_rgo_queue_request_owner
        has_variable = eu5ab_rgo_queue_request_day has_variable_list = eu5ab_rgo_queue_tickets }
        owner = var:eu5ab_rgo_queue_request_owner
        var:eu5ab_rgo_queue_request_day = eu5ab_pl_today
    }
}
eu5ab_rgo_queue_failed_current = {
    exists = var:eu5ab_rgo_queue_failed_owner has_variable = eu5ab_rgo_queue_failed_day
    trigger_if = { limit = { exists = var:eu5ab_rgo_queue_failed_owner has_variable = eu5ab_rgo_queue_failed_day }
        owner = var:eu5ab_rgo_queue_failed_owner
        var:eu5ab_rgo_queue_failed_day = eu5ab_pl_today
    }
}
# The native duration is a first staffing-inspection time, never proof of completion.
# Older, already-completed records can proceed without inventing a past date.
eu5ab_rgo_pending_staffing_due = {
    NOT = { has_variable = eu5ab_rgo_pending_wait_construction }
    OR = {
        eu5ab_rgos_under_construction = 0
        AND = {
            has_variable = eu5ab_rgo_pending_baseline
            trigger_if = { limit = { has_variable = eu5ab_rgo_pending_baseline }
                rgo_level > var:eu5ab_rgo_pending_baseline
            }
        }
    }
}
'''


def render_effects() -> str:
    return '''
eu5ab_request_rgo_timing = {
    if = { limit = { exists = var:eu5ab_rgo_pending_owner }
        if = { limit = { OR = { eu5ab_rgos_under_construction = 0
            has_variable = eu5ab_rgo_pending_ambiguous has_variable = eu5ab_rgo_pending_level_loss } }
            var:eu5ab_rgo_pending_owner = {
                remove_list_variable = { name = eu5ab_rgo_timing_requests target = prev }
            }
        }
    }
    if = { limit = { exists = var:eu5ab_rgo_pending_owner
        has_variable = eu5ab_rgo_pending_levels
        trigger_if = { limit = { has_variable = eu5ab_rgo_pending_levels } var:eu5ab_rgo_pending_levels = 1 }
        NOT = { has_variable = eu5ab_rgo_pending_timing_ready }
        NOT = { has_variable = eu5ab_rgo_pending_ambiguous }
        NOT = { has_variable = eu5ab_rgo_pending_level_loss }
        NOT = { eu5ab_rgos_under_construction = 0 } }
        if = { limit = { owner = var:eu5ab_rgo_pending_owner }
            owner = { if = { limit = { NOT = {
                is_target_in_variable_list = { name = eu5ab_rgo_timing_requests target = prev }
            } } add_to_variable_list = { name = eu5ab_rgo_timing_requests target = prev } } }
        }
    }
}
eu5ab_clear_rgo_queue = {
    remove_variable = eu5ab_rgo_queue_ready
    remove_variable = eu5ab_rgo_queue_count
    remove_variable = eu5ab_rgo_queue_owner
    remove_variable = eu5ab_rgo_queue_day
    remove_variable = eu5ab_rgo_queue_civil
    remove_variable = eu5ab_rgo_queue_level
    remove_variable = eu5ab_rgo_queue_failed_day
    remove_variable = eu5ab_rgo_queue_failed_owner
}
eu5ab_stamp_rgo_queue = {
    set_variable = eu5ab_rgo_queue_ready
    set_variable = { name = eu5ab_rgo_queue_owner value = owner }
    set_variable = { name = eu5ab_rgo_queue_day value = eu5ab_pl_today }
    set_variable = { name = eu5ab_rgo_queue_civil value = num_civil_constructions }
    set_variable = { name = eu5ab_rgo_queue_level value = rgo_level }
}
eu5ab_capture_rgo_queue = {
    eu5ab_clear_rgo_queue = yes
    if = { limit = { exists = scope:eu5ab_engine_rgo_count
        scope:eu5ab_engine_rgo_count >= 0
        scope:eu5ab_engine_rgo_count <= num_civil_constructions }
        set_variable = { name = eu5ab_rgo_queue_count value = scope:eu5ab_engine_rgo_count }
        eu5ab_stamp_rgo_queue = yes
    }
    else = {
        set_variable = { name = eu5ab_rgo_queue_failed_day value = eu5ab_pl_today }
        set_variable = { name = eu5ab_rgo_queue_failed_owner value = owner }
    }
}
# Called only after the synchronous command proved native success. A queued
# level adds one; an instant completion adds no queue entry. Never infer from
# all civil projects outside that single command's transaction.
eu5ab_update_rgo_queue_after_start = {
    eu5ab_clear_rgo_queue = yes
    if = { limit = { has_variable = eu5ab_rgo_start_queue_known
        rgo_level >= var:eu5ab_rgo_start_level
        rgo_level <= { value = var:eu5ab_rgo_start_level add = 1 } }
        set_variable = { name = eu5ab_rgo_queue_count value = { value = 1
            if = { limit = { has_variable = eu5ab_rgo_start_queue } add = var:eu5ab_rgo_start_queue }
            add = var:eu5ab_rgo_start_level subtract = rgo_level } }
        eu5ab_stamp_rgo_queue = yes
    }
}
eu5ab_capture_rgo_start_queue = {
    remove_variable = eu5ab_rgo_start_queue_known
    set_variable = { name = eu5ab_rgo_start_queue value = eu5ab_rgos_under_construction }
    if = { limit = { eu5ab_rgos_under_construction >= 0 } set_variable = eu5ab_rgo_start_queue_known }
}
eu5ab_request_rgo_queue = {
    if = { limit = { num_civil_constructions > 0 exists = owner
        NOT = { eu5ab_rgo_queue_failed_current = yes }
        NOT = { eu5ab_rgo_queue_request_current = yes } }
        if = { limit = { exists = var:eu5ab_rgo_queue_request_owner }
            var:eu5ab_rgo_queue_request_owner = {
                remove_list_variable = { name = eu5ab_rgo_queue_requests target = prev }
            }
        }
        set_variable = { name = eu5ab_rgo_queue_sequence value = { value = 1
            if = { limit = { has_variable = eu5ab_rgo_queue_sequence } add = var:eu5ab_rgo_queue_sequence } } }
        set_variable = { name = eu5ab_rgo_queue_request_owner value = owner }
        set_variable = { name = eu5ab_rgo_queue_request_day value = eu5ab_pl_today }
        clear_variable_list = eu5ab_rgo_queue_tickets
        add_to_variable_list = { name = eu5ab_rgo_queue_tickets target = var:eu5ab_rgo_queue_sequence }
        owner = { if = { limit = { NOT = { is_target_in_variable_list = { name = eu5ab_rgo_queue_requests target = prev } } }
            add_to_variable_list = { name = eu5ab_rgo_queue_requests target = prev }
        } }
    }
}
'''


def render_guis() -> str:
    return '''
# Timing only: never adopts a project or marks one complete. A matching single
# non-estate RGO in an unmixed confirmed record is the native duration source.
eu5ab_gui_capture_rgo_timing = {
    saved_scopes = { eu5ab_engine_country eu5ab_engine_rgo_count eu5ab_engine_rgo_days }
    is_valid = { always = yes }
    effect = {
        if = { limit = { exists = scope:eu5ab_engine_country
            exists = scope:eu5ab_engine_rgo_days exists = scope:eu5ab_engine_rgo_count
            exists = var:eu5ab_rgo_pending_owner has_variable = eu5ab_rgo_pending_good
            has_variable = eu5ab_rgo_pending_baseline has_variable = eu5ab_rgo_pending_levels
            NOT = { has_variable = eu5ab_rgo_pending_timing_ready }
            NOT = { has_variable = eu5ab_rgo_pending_ambiguous }
            NOT = { has_variable = eu5ab_rgo_pending_level_loss }
        }
            if = { limit = { owner = scope:eu5ab_engine_country
                var:eu5ab_rgo_pending_owner = scope:eu5ab_engine_country
                raw_material = var:eu5ab_rgo_pending_good
                rgo_level = var:eu5ab_rgo_pending_baseline
                var:eu5ab_rgo_pending_levels = 1 scope:eu5ab_engine_rgo_count = 1
                scope:eu5ab_engine_rgo_days >= 0 scope:eu5ab_engine_rgo_days <= 36500
                owner = { is_target_in_variable_list = { name = eu5ab_rgo_timing_requests target = prev } }
            }
                set_variable = { name = eu5ab_rgo_pending_build_days value = scope:eu5ab_engine_rgo_days }
                if = { limit = { scope:eu5ab_engine_rgo_days > 0 }
                    # Engine duration handles real calendar days, including
                    # month lengths; eu5ab_pl_today is only an ordering stamp.
                    set_variable = { name = eu5ab_rgo_pending_wait_construction value = 1 days = eu5ab_rgo_pending_wait_days }
                }
                set_variable = eu5ab_rgo_pending_timing_ready
                owner = { remove_list_variable = { name = eu5ab_rgo_timing_requests target = prev } }
            }
        }
    }
}
eu5ab_gui_capture_pending_rgo_queue = {
    saved_scopes = { eu5ab_engine_country eu5ab_rgo_queue_ticket eu5ab_engine_rgo_count }
    is_valid = { always = yes }
    effect = {
        if = { limit = {
            exists = scope:eu5ab_rgo_queue_ticket
            exists = scope:eu5ab_engine_country
            has_variable = eu5ab_rgo_queue_sequence
            exists = var:eu5ab_rgo_queue_request_owner
            has_variable = eu5ab_rgo_queue_request_day
            has_variable_list = eu5ab_rgo_queue_tickets
        }
        if = { limit = {
            scope:eu5ab_rgo_queue_ticket = var:eu5ab_rgo_queue_sequence
            var:eu5ab_rgo_queue_request_owner = scope:eu5ab_engine_country
            is_target_in_variable_list = { name = eu5ab_rgo_queue_tickets target = scope:eu5ab_rgo_queue_ticket }
        }
            clear_variable_list = eu5ab_rgo_queue_tickets
            remove_variable = eu5ab_rgo_queue_request_owner
            scope:eu5ab_engine_country = { remove_list_variable = { name = eu5ab_rgo_queue_requests target = prev } }
            if = { limit = { owner = scope:eu5ab_engine_country
                var:eu5ab_rgo_queue_request_day = eu5ab_pl_today }
                eu5ab_capture_rgo_queue = yes
                # Refresh the registered project's old contribution in place.
                # A failed reading preserves its unknown reservation.
                eu5ab_prepare_rgo_pending_start = yes
            }
            remove_variable = eu5ab_rgo_queue_request_day
        }
        }
    }
}
'''


def render_widget() -> str:
    args = ("GuiScope.SetRoot(Location.MakeScope).AddScope('eu5ab_engine_country', GetPlayer.MakeScope)"
            ".AddScope('eu5ab_rgo_queue_ticket', MakeScopeValue(Scope.GetValue))" + gui_arguments() + '.End')
    timing_args = ("GuiScope.SetRoot(Construction.GetLocation.MakeScope)"
        ".AddScope('eu5ab_engine_country', GetPlayer.MakeScope)"
        ".AddScope('eu5ab_engine_rgo_count', MakeScopeValue("
        + nonnegative_int32('Construction.GetLocation.GetMaxRGOWorkersUnderConstruction') + '))'
        ".AddScope('eu5ab_engine_rgo_days', MakeScopeValue("
        + nonnegative_int32('Construction.GetDurationInDaysIncludingQueue') + ')).End')
    return '''
        widget = {
            datamodel = "[GetPlayer.MakeScope.GetList('eu5ab_rgo_timing_requests')]"
            item = { widget = {
                datacontext = "[Scope.GetLocation]"
                datamodel = "[Location.GetCivilConstructions]"
                item = { widget = {
                    visible_at_creation = no
                    visible = "[And(Construction.IsRGO, Not(Construction.IsBuiltByEstate))]"
                    state = { name = _show duration = 0.01
                        on_finish = "[GetScriptedGui('eu5ab_gui_capture_rgo_timing').Execute(''' + timing_args + ''')]"
                    }
                } }
            } }
        }
        widget = {
            datamodel = "[GetPlayer.MakeScope.GetList('eu5ab_rgo_queue_requests')]"
            item = { widget = {
                datacontext = "[Scope.GetLocation]"
                datamodel = "[Location.MakeScope.GetList('eu5ab_rgo_queue_tickets')]"
                item = { widget = {
                    visible_at_creation = no
                    visible = "[GetPlayer.Exists]"
                    state = { name = _show duration = 0.01
                        on_finish = "[GetScriptedGui('eu5ab_gui_capture_pending_rgo_queue').Execute(''' + args + ''')]"
                    }
                } }
            } }
        }
'''
