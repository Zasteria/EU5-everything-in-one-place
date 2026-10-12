"""Native parallel construction capacity, independent of staffed-building caps.

Coarse scans read the final location modifier. With an existing civil queue,
the GUI compares native queue occupancy against its native limit and sends the
count through fixed literals. A valid capture authorizes only the next slot;
another project needs a fresh capture. Missing or inconsistent reads fail
closed. Empty queues need only their first slot.
"""
import math
from . import queue_bridge


MAX_GUI_QUEUE_COUNT = 16


def remaining(limit: float | None, occupied: int, reserved: int = 0) -> int:
    if (limit is None or not math.isfinite(limit) or limit < 1 or
            occupied < 0 or reserved < 0):
        return 0
    return max(0, math.floor(limit) - occupied - reserved)


GUI_SCOPES = "eu5ab_engine_parallel_modifier"


def gui_arguments() -> str:
    return ".AddScope('eu5ab_engine_parallel_modifier', MakeScopeValue(Location.GetModifierValueFixed('max_constructions_at_same_time')))"


def render() -> tuple[str, str, str, str]:
    effects = '''eu5ab_clear_parallel_capacity = {
    remove_variable = eu5ab_parallel_limit
    remove_variable = eu5ab_parallel_occupied
    remove_variable = eu5ab_parallel_modifier
    remove_variable = eu5ab_parallel_owner
}
eu5ab_capture_parallel_queue = {
    eu5ab_clear_parallel_capacity = yes
    if = {
        limit = {
            exists = scope:eu5ab_engine_queue_count
            exists = scope:eu5ab_engine_queue_has_room
            exists = scope:eu5ab_engine_parallel_modifier
            scope:eu5ab_engine_queue_has_room = yes
            scope:eu5ab_engine_queue_count = num_civil_constructions
            scope:eu5ab_engine_queue_count > 0
            scope:eu5ab_engine_parallel_modifier = modifier:max_constructions_at_same_time
        }
        # The GUI proves only that the next native slot is open. Require a new
        # sample after a start rather than inferring all remaining slots.
        set_variable = { name = eu5ab_parallel_limit value = { value = scope:eu5ab_engine_queue_count add = 1 } }
        set_variable = { name = eu5ab_parallel_occupied value = scope:eu5ab_engine_queue_count }
        set_variable = { name = eu5ab_parallel_modifier value = scope:eu5ab_engine_parallel_modifier }
        set_variable = { name = eu5ab_parallel_owner value = owner }
    }
}
'''
    triggers = '''# Cheap scan gate. Final approval/fire use a fresh native next-slot proof.
eu5ab_location_has_parallel_room = {
    modifier:max_constructions_at_same_time >= 1
    num_civil_constructions < modifier:max_constructions_at_same_time
}
eu5ab_parallel_capture_current = {
    exists = var:eu5ab_parallel_owner
    owner = var:eu5ab_parallel_owner
    has_variable = eu5ab_parallel_limit
    has_variable = eu5ab_parallel_occupied
    has_variable = eu5ab_parallel_modifier
    var:eu5ab_parallel_limit = eu5ab_parallel_next_slot_value
    var:eu5ab_parallel_occupied = num_civil_constructions
    var:eu5ab_parallel_modifier = modifier:max_constructions_at_same_time
}
eu5ab_location_has_native_parallel_room = {
    OR = {
        AND = { num_civil_constructions = 0 modifier:max_constructions_at_same_time >= 1 }
        AND = { eu5ab_parallel_capture_current = yes num_civil_constructions < var:eu5ab_parallel_limit }
    }
}
eu5ab_engine_has_parallel_room = {
    exists = scope:eu5ab_engine_parallel_modifier
    scope:eu5ab_engine_parallel_modifier = modifier:max_constructions_at_same_time
    # The script reads current occupancy directly. Nonempty queues also require
    # the captured native CountAllInLocation to match that live count.
    eu5ab_location_has_native_parallel_room = yes
}
'''
    values = '''eu5ab_queue_before_attempt_value = { value = 0 if = { limit = { has_variable = eu5ab_queue_before_attempt } add = var:eu5ab_queue_before_attempt } }
eu5ab_parallel_next_slot_value = { value = num_civil_constructions add = 1 }
eu5ab_parallel_remaining = {
    value = 0
    if = {
        limit = { num_civil_constructions = 0 modifier:max_constructions_at_same_time >= 1 }
        value = modifier:max_constructions_at_same_time
        floor = yes
    }
    else_if = {
        limit = { eu5ab_parallel_capture_current = yes }
        value = var:eu5ab_parallel_limit
        subtract = num_civil_constructions
        min = 0
    }
}
'''
    guis = '''eu5ab_gui_capture_parallel_queue = {
    saved_scopes = { eu5ab_engine_country eu5ab_engine_queue_count eu5ab_engine_queue_has_room ''' + GUI_SCOPES + ''' }
    is_valid = { always = yes }
    effect = {
        if = {
            limit = { owner = scope:eu5ab_engine_country OR = {
                has_variable = eu5ab_capacity_requested
                owner = { has_variable = eu5ab_q_active }
            } }
            eu5ab_capture_parallel_queue = yes
        }
    }
}
eu5ab_gui_clear_parallel_queue = {
    saved_scopes = { eu5ab_engine_country }
    is_valid = { always = yes }
    effect = {
        if = {
            limit = { owner = scope:eu5ab_engine_country OR = {
                has_variable = eu5ab_capacity_requested
                owner = { has_variable = eu5ab_q_active }
            } }
            eu5ab_clear_parallel_capacity = yes
        }
    }
}
'''
    # Workers carry their own capacity ticket. Legacy queue readers retain
    # compatibility, but cannot accept a stale capacity callback through it.
    old_guard = '''owner = scope:eu5ab_engine_country OR = {
                has_variable = eu5ab_capacity_requested
                owner = { has_variable = eu5ab_q_active }
            }'''
    guard = '''owner = scope:eu5ab_engine_country OR = {
        AND = { NOT = { exists = scope:eu5ab_bridge_ticket } $CAPACITY_RECEIPT$ }
        AND = { NOT = { exists = scope:eu5ab_capacity_ticket }
            owner = { NOT = { has_variable = eu5ab_bridge_schema } has_variable = eu5ab_q_active } }
        AND = { ''' + queue_bridge.READER_LOCATION + ''' scope:eu5ab_engine_country = {
            var:eu5ab_bridge_kind < 4 has_variable = eu5ab_bridge_parallel_needed
            NOT = { has_variable = eu5ab_bridge_parallel_received } } }
    }'''
    receipt = '''if = { limit = { exists = scope:eu5ab_bridge_ticket }
        scope:eu5ab_engine_country = { set_variable = eu5ab_bridge_parallel_received }
        clear_variable_list = eu5ab_bridge_parallel_tickets
    }'''
    from .building_capacity import RECEIPT_CURRENT
    guard = guard.replace('$CAPACITY_RECEIPT$', RECEIPT_CURRENT)
    guis = guis.replace('saved_scopes = {', 'saved_scopes = { eu5ab_capacity_ticket eu5ab_bridge_ticket')
    guis = guis.replace(old_guard, guard).replace('            eu5ab_capture_parallel_queue = yes',
        '            ' + receipt + '\n            eu5ab_capture_parallel_queue = yes').replace(
        '            eu5ab_clear_parallel_capacity = yes', '            ' + receipt + '\n            eu5ab_clear_parallel_capacity = yes')
    return effects, triggers, values, guis


def capture_widget(prefix: str, *, bridge: bool = False, capacity: bool = False) -> str:
    # The engine probe showed that neither native int32 getter can be promoted
    # by MakeScopeValue. GUI int32 predicates and fixed literals are supported.
    args = "GuiScope.SetRoot(Location.MakeScope).AddScope('eu5ab_engine_country', GetPlayer.MakeScope)"
    if bridge:
        args += queue_bridge.ticket_argument()
    if capacity:
        args += ".AddScope('eu5ab_capacity_ticket', MakeScopeValue(Scope.GetValue))"
    neutral = 'visible_at_creation = no state = { name = _hide alpha = 0 } state = { name = _show alpha = 1 }' if bridge else ''
    count_widgets = '\n'.join(f'''
            widget = {{
                {neutral}
                visible = "[EqualTo_int32(Construction.CountAllInLocation, '(int32){count}')]"
                state = {{ name = {prefix}_sample on_finish = "[GetScriptedGui('eu5ab_gui_capture_parallel_queue').Execute({args}.AddScope('eu5ab_engine_queue_count', MakeScopeValue('(CFixedPoint){count}')).AddScope('eu5ab_engine_queue_has_room', MakeScopeBool(LessThan_int32(Construction.CountAllInLocation, Construction.GetMaxParallelInQueue))){gui_arguments()}.End)]" }}
            }}''' for count in range(1, MAX_GUI_QUEUE_COUNT + 1))
    selectors = f'''
{count_widgets}
            widget = {{
                {neutral}
                visible = "[GreaterThan_int32(Construction.CountAllInLocation, '(int32){MAX_GUI_QUEUE_COUNT}')]"
                state = {{ name = {prefix}_sample on_finish = "[GetScriptedGui('eu5ab_gui_clear_parallel_queue').Execute({args}.End)]" }}
            }}'''
    if bridge:
        selectors = '''widget = { datamodel = "[Location.MakeScope.GetList('eu5ab_bridge_parallel_tickets')]"
            item = { widget = { ''' + selectors + ' } } }'
    elif capacity:
        selectors = '''widget = { datamodel = "[Location.MakeScope.GetList('eu5ab_capacity_tickets')]"
            item = { widget = { ''' + selectors + ' } } }'
    return f'''
    widget = {{
        datamodel = "[DataModelFirst(Location.GetCivilConstructions, '(int32)1')]"
        item = {{ widget = {{
{selectors}
        }} }}
    }}
'''
