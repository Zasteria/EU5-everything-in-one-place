"""Human-only reset and exhaustive monthly planning, with native event lifetime.

The ordinary queue's screening, ranking and reservations are reused. Planning
records approvals without issuing native orders; the exact ordered approvals
and their quotes are restored on the 23rd. UI callbacks, not a blocking loop,
advance the calculation while the confirmation event remains open.
"""
import re
import json
from pathlib import Path

from . import decision_state as state
from .candidate_backfill import _upsert_increment
from .queue_bridge import _block

C = 'scope:eu5ab_engine_country'
L = 'scope:eu5ab_candidate_location'
ID = 'scope:eu5ab_batch_id'
EVENT = 'eu5ab_decisions.2'
PREFIX = 'eu5ab_manual_saved_'
LEGACY_ACTIONS = '# Generated. Entries restored to decisions/eu5ab_decisions.txt.\n'


def body(text, name):
    return _block(text, name).split('{', 1)[1][:-1]


def wrap(text, name, condition, replace, alternative=''):
    return replace(text, name, f'{name} = {{ if = {{ limit = {{ {condition} }}\n{body(text, name)}\n}}{alternative}\n}}')


def render_triggers():
    months = ' '.join(f'AND = {{ current_month = {m} var:eu5ab_manual_month = {m} }}' for m in range(1, 13))
    days = ' '.join(f'current_day = {d}' for d in range(1, 23))
    return f'''eu5ab_manual_month_current = {{ has_variable = eu5ab_manual_year has_variable = eu5ab_manual_month
    var:eu5ab_manual_year = current_year OR = {{ {months} }} }}
eu5ab_manual_date_allowed = {{ OR = {{ {days} }} }}
eu5ab_manual_allowed = {{ is_human = yes
    custom_tooltip = {{ text = eu5ab_manual_before_23 eu5ab_manual_date_allowed = yes }}
    custom_tooltip = {{ text = eu5ab_manual_not_dispatched
        NOT = {{ AND = {{ eu5ab_scan_month_current = yes has_variable = eu5ab_manual_dispatch_started }} }} }}
    NOT = {{ has_variable = eu5ab_manual_computing }}
}}
'''


def render_decisions():
    """Native decision rows; the list GUI opens their confirmation events."""
    return '''# Generated. Exactly two human-only decisions.
eu5ab_reset_decision = {
    decision_category = other_decisions
    potential = { is_human = yes }
    allow = { is_human = yes NOT = { has_variable = eu5ab_manual_event_open } }
    ai_will_do = { value = 0 }
    option = { name = eu5ab_open_confirmation
        effect = { trigger_event_silently = eu5ab_decisions.1 } }
}
eu5ab_deep_decision = {
    decision_category = economy_decisions
    potential = { is_human = yes }
    allow = { eu5ab_manual_allowed = yes NOT = { has_variable = eu5ab_manual_event_open } }
    ai_will_do = { value = 0 }
    option = { name = eu5ab_open_confirmation
        effect = { trigger_event_silently = eu5ab_decisions.2 } }
}
'''


def render_events():
    return '''namespace = eu5ab_decisions
eu5ab_decisions.1 = {
    type = country_event
    outcome = neutral
    title = eu5ab_reset_decision
    desc = eu5ab_reset_confirm_desc
    interface_lock = yes
    image = "gfx/interface/illustrations/event/backgrounds/special/shortage.dds"
    trigger = { is_human = yes }
    immediate = { set_variable = eu5ab_manual_event_open }
    option = { name = eu5ab_reset_confirm eu5ab_profile_reset = yes }
    option = { name = eu5ab_decision_cancel remove_variable = eu5ab_manual_event_open }
}
eu5ab_decisions.2 = {
    type = country_event
    outcome = neutral
    title = eu5ab_deep_decision
    desc = eu5ab_deep_confirm_desc
    interface_lock = yes
    image = "gfx/interface/illustrations/event/backgrounds/exterior/burghers/asian_burghers_exterior.dds"
    trigger = { eu5ab_manual_allowed = yes }
    immediate = { set_variable = eu5ab_manual_event_open remove_variable = eu5ab_manual_event_started }
    # Dedicated GUI starts the calculation without selecting an event option.
    # These options only dismiss the native event after cancellation/completion.
    option = { name = eu5ab_deep_event_finish
        if = { limit = { has_variable = eu5ab_manual_ready }
            remove_variable = eu5ab_manual_event_open remove_variable = eu5ab_manual_event_started } }
    option = { name = eu5ab_deep_event_cancel
        if = { limit = { NOT = { has_variable = eu5ab_manual_event_started } }
            remove_variable = eu5ab_manual_event_open } }
}
eu5ab_decisions.3 = {
    type = country_event hidden = yes
    title = eu5ab_deep_decision
    outcome = neutral
    immediate = {
        eu5ab_manual_expire = yes
        if = { limit = { eu5ab_manual_month_current = yes NOT = { has_variable = eu5ab_manual_executed } }
            if = { limit = { has_variable = eu5ab_manual_ready eu5ab_manual_date_allowed = no }
                eu5ab_manual_execute = yes }
            else = { trigger_event_silently = { id = eu5ab_decisions.3 days = 1 } }
        }
    }
}
'''


def render_core(config, snapshot_fields):
    # The synchronous dispatcher guard is execution state, not plan data.
    # Keep the live guard intact while finishing inside the dispatcher.
    snapshot_fields = (tuple(n for n in snapshot_fields[0] if n != 'eu5ab_batch_running'),
                       *snapshot_fields[1:])
    rename = lambda n: PREFIX + n
    saved = state.rename_state(snapshot_fields, rename)
    config_copy = state.copy_state(config, C, C, rename)
    save = state.copy_state(snapshot_fields, 'scope:eu5ab_manual_copy', 'scope:eu5ab_manual_copy', rename)
    restore = state.copy_state(saved, 'scope:eu5ab_manual_copy', 'scope:eu5ab_manual_copy', lambda n: n.removeprefix(PREFIX))
    config_saved = state.rename_state(config, rename)
    cleanup = state.clear_state(tuple(tuple(sorted(set(a) | set(b))) for a, b in zip(saved, config_saved)))
    stamp = ' '.join(f'if = {{ limit = {{ current_month = {m} }} set_variable = {{ name = eu5ab_manual_month value = {m} }} }}' for m in range(1, 13))
    return f'''
eu5ab_manual_discard = {{
    save_scope_as = eu5ab_engine_country
    every_in_list = {{ variable = eu5ab_manual_locations limit = {{ owner = {C} }}
        {cleanup}
        remove_variable = eu5ab_manual_policy remove_variable = eu5ab_manual_slot
        remove_variable = eu5ab_manual_location remove_variable = eu5ab_manual_location_owner
    }}
    {cleanup}
    clear_variable_list = eu5ab_manual_locations clear_variable_list = eu5ab_manual_plan
    clear_variable_map = eu5ab_manual_plan_kind
    remove_variable = eu5ab_manual_computing remove_variable = eu5ab_manual_ready
    remove_variable = eu5ab_manual_sampling
    remove_variable = eu5ab_manual_expired
    remove_variable = eu5ab_manual_month remove_variable = eu5ab_manual_year
    remove_variable = eu5ab_manual_executed remove_variable = eu5ab_manual_dispatch_started
    remove_variable = eu5ab_manual_budget_limit
    remove_variable = eu5ab_manual_count remove_variable = eu5ab_manual_cost
}}
eu5ab_manual_expire = {{
    if = {{ limit = {{ has_variable = eu5ab_manual_year NOT = {{ eu5ab_manual_month_current = yes }} }}
        eu5ab_manual_discard = yes eu5ab_sync_cmm_settings = yes eu5ab_refresh_global_budget = yes
        if = {{ limit = {{ has_variable = eu5ab_manual_event_open has_variable = eu5ab_manual_event_started }}
            set_variable = eu5ab_manual_expired set_variable = eu5ab_manual_ready }}
    }}
}}
eu5ab_manual_begin = {{
    if = {{ limit = {{ eu5ab_manual_allowed = yes has_variable = eu5ab_manual_event_open
        NOT = {{ has_variable = eu5ab_manual_event_started }} }}
        save_scope_as = actor save_scope_as = eu5ab_engine_country save_scope_as = eu5ab_scan_country
        eu5ab_manual_discard = yes
        # No native orders can have started before the date gate.
        eu5ab_clear_engine_candidate_queue = yes eu5ab_clear_scan_continuation = yes
        every_in_list = {{ variable = eu5ab_worker_pending_locations limit = {{ owner = {C} }}
            eu5ab_clear_location_worker_state = yes eu5ab_clear_location_candidate_state = yes }}
        clear_variable_list = eu5ab_worker_pending_locations
        remove_variable = eu5ab_scan_active remove_variable = eu5ab_scan_finalizing
        remove_variable = eu5ab_scan_resume_after_load
        eu5ab_sync_cmm_settings = yes eu5ab_refresh_global_budget = yes
        {config_copy}
        set_variable = {{ name = eu5ab_manual_budget_limit value = eu5ab_global_budget_limit_value }}
        set_variable = {{ name = eu5ab_manual_year value = current_year }} {stamp}
        set_variable = eu5ab_manual_computing set_variable = eu5ab_manual_event_started
        set_variable = eu5ab_manual_sampling
        eu5ab_run_regional_development_policy = yes
        # Exhaustive dispatch bypasses the normal bucket's date and counters.
        eu5ab_record_scan_date = yes
        set_variable = eu5ab_scan_active set_variable = eu5ab_scan_finalizing
        every_owned_location = {{
            limit = {{ has_variable = eu5ab_policy_id eu5ab_location_template_not_paused = yes }}
            save_scope_as = eu5ab_candidate_location
            eu5ab_clear_location_worker_state = yes eu5ab_clear_location_candidate_state = yes
            set_variable = {{ name = eu5ab_manual_policy value = var:eu5ab_policy_id }}
            if = {{ limit = {{ has_variable = eu5ab_template_slot }}
                set_variable = {{ name = eu5ab_manual_slot value = var:eu5ab_template_slot }} }}
            set_variable = eu5ab_manual_location
            set_variable = {{ name = eu5ab_manual_location_owner value = owner }}
            set_variable = {{ name = eu5ab_cached_location_need_score value = eu5ab_location_need_score }}
            {C} = {{ add_to_variable_list = {{ name = eu5ab_manual_locations target = {L} }}
                add_to_variable_list = {{ name = eu5ab_worker_pending_locations target = {L} }}
                {_upsert_increment('eu5ab_diag_preliminary_passed')}
                {_upsert_increment('eu5ab_diag_deep_scored')} }}
            eu5ab_prepare_backfill_dispatch = yes eu5ab_request_building_capacity = yes
        }}
        if = {{ limit = {{ NOT = {{ has_variable_list = eu5ab_worker_pending_locations }} }}
            eu5ab_finish_regional_development_scan = yes }}
        trigger_event_silently = {{ id = eu5ab_decisions.3 days = 1 }}
    }}
}}
eu5ab_manual_remember_buildings = {{
    every_in_list = {{ variable = eu5ab_batch_approved save_scope_value_as = {{ name = eu5ab_batch_id value = this }}
        {C} = {{
            add_to_variable_list = {{ name = eu5ab_manual_plan target = {ID} }}
            add_to_variable_map = {{ name = eu5ab_manual_plan_kind key = {ID} value = 1 }}
            add_to_variable_map = {{ name = eu5ab_batch_status key = {ID} value = 9 }}
            eu5ab_batch_select_context = yes
            # Preserve expansion behavior, consuming a distinct ID and slot.
            if = {{ limit = {{ {L}.eu5ab_batch_quote_kind = 4 {L}.eu5ab_batch_slots_value > 0
                eu5ab_batch_reserved_value < var:eu5ab_monthly_build_quota
                eu5ab_batch_planned_value < eu5ab_global_budget_remaining_value }}
                {L} = {{ save_scope_as = eu5ab_batch_refresh_location }}
                scope:eu5ab_candidate_building = {{ save_scope_as = eu5ab_batch_refresh_type }}
                {L} = {{ eu5ab_batch_refresh_quote_pending = yes }}
                if = {{ limit = {{ {L}.eu5ab_batch_quote_pending_open > 0 }} eu5ab_batch_add_candidate = yes }}
            }}
        }}
    }}
    clear_variable_list = eu5ab_batch_approved
}}
eu5ab_manual_remember_rgos = {{
    every_in_list = {{ variable = eu5ab_batch_rgo_approved save_scope_value_as = {{ name = eu5ab_batch_id value = this }}
        {C} = {{ add_to_variable_list = {{ name = eu5ab_manual_plan target = {ID} }}
            add_to_variable_map = {{ name = eu5ab_manual_plan_kind key = {ID} value = 2 }}
            add_to_variable_map = {{ name = eu5ab_batch_rgo_status key = {ID} value = 9 }} }} }}
    clear_variable_list = eu5ab_batch_rgo_approved
}}
eu5ab_manual_finish = {{
    # All phases reached a real terminal condition, not a GUI timeout.
    save_scope_as = eu5ab_engine_country save_scope_as = eu5ab_manual_copy
    # Zero is also persisted by the engine; do not rely on has_variable alone
    # to publish completion. Preserve genuine no-coverage/quota/eligible states.
    if = {{ limit = {{ NOT = {{ has_variable = eu5ab_diag_run_state }} }}
        set_variable = {{ name = eu5ab_diag_run_state value = 5 }} }}
    else_if = {{ limit = {{ var:eu5ab_diag_run_state = 0 }}
        set_variable = {{ name = eu5ab_diag_run_state value = 5 }} }}
    set_variable = {{ name = eu5ab_manual_count value = eu5ab_batch_reserved_value }}
    set_variable = {{ name = eu5ab_manual_cost value = eu5ab_batch_planned_value }}
    {save}
    every_in_list = {{ variable = eu5ab_manual_locations limit = {{ owner = {C} }}
        save_scope_as = eu5ab_manual_copy {save} }}
    remove_variable = eu5ab_manual_computing remove_variable = eu5ab_manual_sampling set_variable = eu5ab_manual_ready
    # Teardown releases scratch but cannot touch the saved plan or its quotes.
    eu5ab_finish_engine_candidate_queue_live = yes
}}
eu5ab_manual_restore_scope = {{ save_scope_as = eu5ab_manual_copy {restore} }}
eu5ab_manual_recover = {{
    # No day must pass for pending GUI reads to resume behind the native event.
    save_scope_as = actor save_scope_as = eu5ab_engine_country
    remove_variable = eu5ab_scan_resume_after_load remove_variable = eu5ab_batch_running
    if = {{ limit = {{ has_variable = eu5ab_manual_computing }}
        every_in_list = {{ variable = eu5ab_worker_pending_locations
            limit = {{ owner = {C} NOT = {{ has_variable = eu5ab_worker_complete }} }}
            eu5ab_request_building_capacity = yes }}
        eu5ab_clear_queue_bridge = yes
        if = {{ limit = {{ has_variable = eu5ab_q_active }}
            set_variable = eu5ab_bridge_rebuild eu5ab_dispatch_construction_batch = yes }}
        else = {{ eu5ab_reduce_capacity_batch = yes }}
    }}
}}
eu5ab_manual_execute = {{
    if = {{ limit = {{ is_human = yes eu5ab_manual_month_current = yes
        eu5ab_manual_date_allowed = no has_variable = eu5ab_manual_ready
        NOT = {{ has_variable = eu5ab_manual_executed }} }}
        save_scope_as = actor save_scope_as = eu5ab_engine_country
        set_variable = eu5ab_manual_executed set_variable = eu5ab_manual_dispatch_started
        eu5ab_manual_restore_scope = yes
        every_in_list = {{ variable = eu5ab_manual_locations limit = {{ owner = {C} }} eu5ab_manual_restore_scope = yes }}
        set_variable = eu5ab_batch_schema set_variable = eu5ab_q_active
        set_variable = {{ name = eu5ab_constructions_started_this_tick value = 0 }}
        every_in_list = {{ variable = eu5ab_manual_plan save_scope_value_as = {{ name = eu5ab_batch_id value = this }}
            {C} = {{
                clear_variable_list = eu5ab_batch_approved clear_variable_list = eu5ab_batch_rgo_approved
                set_variable = {{ name = eu5ab_batch_reserved value = 1 }}
                if = {{ limit = {{ "variable_map(eu5ab_manual_plan_kind|{ID})" = 1 }}
                    set_variable = {{ name = eu5ab_q_phase value = "variable_map(eu5ab_batch_phase|{ID})" }}
                    set_variable = {{ name = eu5ab_batch_planned value = "variable_map(eu5ab_batch_cost|{ID})" }}
                    add_to_variable_map = {{ name = eu5ab_batch_status key = {ID} value = 2 }}
                    add_to_variable_list = {{ name = eu5ab_batch_approved target = {ID} }}
                    if = {{ limit = {{ "variable_map(eu5ab_batch_location|{ID})" = {{ owner = {C} }} }}
                        eu5ab_batch_issue_live = yes }}
                    else = {{ add_to_variable_map = {{ name = eu5ab_batch_status key = {ID} value = 7 }} }}
                }}
                else = {{
                    set_variable = {{ name = eu5ab_q_phase value = "variable_map(eu5ab_batch_rgo_phase|{ID})" }}
                    set_variable = {{ name = eu5ab_batch_planned value = "variable_map(eu5ab_batch_rgo_cost|{ID})" }}
                    add_to_variable_map = {{ name = eu5ab_batch_rgo_status key = {ID} value = 2 }}
                    add_to_variable_list = {{ name = eu5ab_batch_rgo_approved target = {ID} }}
                    if = {{ limit = {{ "variable_map(eu5ab_batch_rgo_location|{ID})" = {{ owner = {C} }} }}
                        eu5ab_batch_rgo_issue_live = yes }}
                    else = {{ add_to_variable_map = {{ name = eu5ab_batch_rgo_status key = {ID} value = 7 }} }}
                }}
            }}
        }}
        eu5ab_finish_engine_candidate_queue_live = yes
    }}
}}
'''


def freeze_values(values, config, replace):
    """Read frozen settings for this month; UI writes still update live settings."""
    numeric = [n for n in config[0] if n.startswith(('eu5ab_global_', 'eu5ab_candidate_priority_'))
               or n == 'eu5ab_monthly_build_hard_cap' or ('var:' + n) in values]
    wrappers = []
    for name in numeric:
        getter = 'eu5ab_manual_value_' + name.removeprefix('eu5ab_')
        values = re.sub(r'var:' + re.escape(name) + r'\b', getter, values)
        wrappers.append(f'''{getter} = {{ value = 0
            if = {{ limit = {{ eu5ab_manual_month_current = yes }}
                if = {{ limit = {{ has_variable = {PREFIX + name} }} add = var:{PREFIX + name} }} }}
            else_if = {{ limit = {{ has_variable = {name} }} add = var:{name} }} }}''')
    for name in ('eu5ab_current_candidate_configured_priority', *(f'eu5ab_score_template_slot_{s}' for s in range(1, 21))):
        old = _block(values, name)
        frozen = re.sub(r'\beu5ab_tpl_(\d+)_building_priorities\b', PREFIX + r'eu5ab_tpl_\1_building_priorities', old)
        values = replace(values, name, f'''{name} = {{ value = 0
            if = {{ limit = {{ {L}.owner = {{ eu5ab_manual_month_current = yes }} }} value = {name}_manual }}
            else = {{ value = {name}_live }} }}''')
        wrappers += [old.replace(name + ' =', name + '_live =', 1), frozen.replace(name + ' =', name + '_manual =', 1)]
    for field, stored in (('policy_id', 'policy'), ('template_slot', 'slot')):
        getter = 'eu5ab_manual_' + stored + '_value'
        values = re.sub(r'var:eu5ab_' + field + r'\b', getter, values)
        wrappers = [re.sub(r'var:eu5ab_' + field + r'\b', getter, v) for v in wrappers]
        wrappers.append(f'''{getter} = {{ value = 0
            if = {{ limit = {{ has_variable = eu5ab_manual_location exists = var:eu5ab_manual_location_owner
                owner = var:eu5ab_manual_location_owner owner = {{ eu5ab_manual_month_current = yes }} }}
                if = {{ limit = {{ has_variable = eu5ab_manual_{stored} }} add = var:eu5ab_manual_{stored} }} }}
            else_if = {{ limit = {{ has_variable = eu5ab_{field} }} add = var:eu5ab_{field} }} }}''')
    return values + '\n' + '\n'.join(wrappers)


def render_guis():
    return '''eu5ab_gui_open_reset_confirmation = {
    is_shown = { is_human = yes }
    is_valid = { is_human = yes NOT = { has_variable = eu5ab_manual_event_open } }
    effect = { trigger_event_silently = eu5ab_decisions.1 }
}
eu5ab_gui_open_deep_confirmation = {
    is_shown = { is_human = yes }
    is_valid = { eu5ab_manual_allowed = yes NOT = { has_variable = eu5ab_manual_event_open } }
    effect = { trigger_event_silently = eu5ab_decisions.2 }
}
eu5ab_gui_manual_begin = {
    is_shown = { has_variable = eu5ab_manual_event_open NOT = { has_variable = eu5ab_manual_event_started } }
    is_valid = { eu5ab_manual_allowed = yes has_variable = eu5ab_manual_event_open NOT = { has_variable = eu5ab_manual_event_started } }
    effect = { eu5ab_manual_begin = yes }
}
eu5ab_gui_manual_waiting = {
    is_shown = { has_variable = eu5ab_manual_event_started NOT = { has_variable = eu5ab_manual_ready } }
}
eu5ab_gui_manual_done = {
    is_shown = { has_variable = eu5ab_manual_event_started has_variable = eu5ab_manual_ready }
    is_valid = { has_variable = eu5ab_manual_event_started has_variable = eu5ab_manual_ready }
}
'''


def render_decisions_window():
    native = (Path(__file__).parent / 'assets' / 'decisions_lateralview_1_4.gui').read_text(encoding='utf-8-sig')
    # Decision has no exported key getter in 1.4. Compare its unformatted name
    # with the same localized .title key the native decision uses, in any language.
    matches = {kind: f"EqualTo_string(DecisionItem.GetDecisionTemplate.GetNameWithNoTooltip, Localize('eu5ab_{kind}_decision.title'))"
               for kind in ('reset', 'deep')}
    special = f"Or({matches['reset']}, {matches['deep']})"
    context = 'GuiScope.SetRoot(Player.MakeScope).End'
    start = native.index('template decision_button_props {')
    end = native.index('\ntypes DecisionsTypes {', start)
    original = native[start:end]
    replacement = original.replace(
        'enabled = "[DecisionItem.IsEnabled]"',
        f'enabled = "[And(DecisionItem.IsEnabled, Or(Not({special}), DecisionItem.IsAllowed))]"', 1)
    replacement = replacement.replace('action_tooltip = {',
        f'action_tooltip = {{\n\t\tvisible = "[Not({special})]"', 1)
    direct = ''
    for kind, match in matches.items():
        callback = f"GetScriptedGui('eu5ab_gui_open_{kind}_confirmation')"
        direct += f'''\taction_tooltip = {{
        visible = "[{match}]"
        click_type = left
        click_mode = single
        title = "eu5ab_open_confirmation"
        enabled = "[And(DecisionItem.IsEnabled, {callback}.IsValid({context}))]"
        conditions = "[{callback}.IsValidTooltip({context})]"
        on_action = "[{callback}.Execute({context})]"
    }}

'''
    replacement = replacement.replace('\ttooltipwidget = {', direct + '\ttooltipwidget = {', 1)
    return native[:start] + replacement + native[end:]


def render_event_window():
    native = (Path(__file__).parent / 'assets' / 'eventwindow_1_4.gui').read_text(encoding='utf-8-sig')
    context = 'GuiScope.SetRoot(Player.MakeScope).End'
    shown = lambda name: f"GetScriptedGui('eu5ab_gui_manual_{name}').IsShown({context})"
    special = f"EqualTo_string(EventWindow.GetEventKey, '{EVENT}')"
    # Both item and scrollwidget require one widget after template expansion.
    # Keep the native option template intact for every other event.
    replacement = f'''template eu5ab_manual_event_option_entry {{
    vbox = {{
    spacing = 8
    ignoreinvisible = yes
    vbox = {{
        visible = "[EventOption.KeyEndWith('_finish')]"
        spacing = 8
        ignoreinvisible = yes
        button_regular_diamond = {{ size = {{ 514 36 }} text = "eu5ab_decision_continue"
            tooltip = "eu5ab_deep_confirm_desc"
            visible = "[{shown('begin')}]"
            enabled = "[And(EventWindow.GetLockableInfo.IsUnlocked, GetScriptedGui('eu5ab_gui_manual_begin').IsValid({context}))]"
            onclick = "[GetScriptedGui('eu5ab_gui_manual_begin').Execute({context})]"
        }}
        text_multi = {{ size = {{ 514 60 }} autoresize = yes align = center
            visible = "[{shown('waiting')}]" text = "eu5ab_manual_waiting" }}
        text_multi = {{ size = {{ 514 70 }} autoresize = yes align = center
            visible = "[{shown('done')}]"
            text = "[Select_CString(Player.MakeScope.GetVariable('eu5ab_manual_expired').IsSet, Localize('eu5ab_manual_expired'), Localize('eu5ab_manual_results'))]" }}
        scrollarea = {{
            size = {{ 514 140 }} visible = "[{shown('done')}]"
            scrollbarpolicy_horizontal = always_off
            scrollbar_vertical = {{ using = Scrollbar_Vertical }}
            scrollwidget = {{
            vbox = {{
                datamodel = "[Player.MakeScope.GetList('eu5ab_manual_plan')]"
                item = {{ vbox = {{ ignoreinvisible = yes
                    text_single = {{ size = {{ 490 24 }} autoresize = no
                        visible = "[EqualTo_CFixedPoint(GetPlayer.MakeScope.GetVariableFromVariableMap('eu5ab_manual_plan_kind', MakeScopeValue(Scope.GetValue)).GetValue, '(CFixedPoint)1')]"
                        raw_text = "[GetPlayer.MakeScope.GetVariableFromVariableMap('eu5ab_manual_saved_eu5ab_batch_location', MakeScopeValue(Scope.GetValue)).GetLocation.GetName] — [GetPlayer.MakeScope.GetVariableFromVariableMap('eu5ab_manual_saved_eu5ab_batch_type', MakeScopeValue(Scope.GetValue)).GetBuildingType.GetName]"
                    }}
                    text_single = {{ size = {{ 490 24 }} autoresize = no
                        visible = "[EqualTo_CFixedPoint(GetPlayer.MakeScope.GetVariableFromVariableMap('eu5ab_manual_plan_kind', MakeScopeValue(Scope.GetValue)).GetValue, '(CFixedPoint)2')]"
                        raw_text = "[GetPlayer.MakeScope.GetVariableFromVariableMap('eu5ab_manual_saved_eu5ab_batch_rgo_location', MakeScopeValue(Scope.GetValue)).GetLocation.GetName] — [Localize('eu5ab_manual_rgo')]"
                    }}
                }} }}
            }}
            }}
        }}
        button_regular_diamond = {{ size = {{ 514 36 }} text = "eu5ab_decision_done"
            tooltip = "eu5ab_decision_done"
            visible = "[{shown('done')}]"
            enabled = "[And(EventWindow.GetLockableInfo.IsUnlocked, GetScriptedGui('eu5ab_gui_manual_done').IsValid({context}))]"
            onclick = "[EventOption.Select]"
        }}
    }}
    button_regular_diamond = {{ size = {{ 514 36 }} text = "eu5ab_decision_cancel"
        tooltip = "eu5ab_decision_cancel"
        visible = "[And(EventOption.KeyEndWith('_cancel'), {shown('begin')})]"
        enabled = "[EventWindow.GetLockableInfo.IsUnlocked]"
        onclick = "[EventOption.Select]"
    }}
    }}
}}'''
    result = native + '\n' + replacement + '\n'
    # Native option grids have fixed 42px rows. Give this event a growing vbox
    # so its waiting/results content cannot overlap the next option or the frame.
    pattern = r'fixedgridbox = \{\s*name = "option_grid"\s*addcolumn = 514\s*addrow = 42\s*datamodel = "\[EventWindow.GetOptions\]"\s*item = \{\s*using = event_option_entry\s*\}\s*\}'
    def option_layout(match):
        ordinary = match[0].replace('fixedgridbox = {', f'fixedgridbox = {{ visible = "[Not({special})]"', 1)
        return f'''vbox = {{ ignoreinvisible = yes
            {ordinary}
            vbox = {{ visible = "[{special}]" spacing = 8 ignoreinvisible = yes
                datamodel = "[EventWindow.GetOptions]"
                item = {{ using = eu5ab_manual_event_option_entry }}
            }}
        }}'''
    result, count = re.subn(pattern, option_layout, result)
    if count != 2: raise ValueError('Native generic event option grids changed')
    return '# EU5 1.4 native event window; only EU5AB deep-event controls differ.\n' + result


def localization(language):
    zh = language == 'simp_chinese'
    entries = {
        'eu5ab_reset_decision': ('重置自动建造', 'Reset Advanced Auto Build'),
        'eu5ab_reset_decision_desc': ('保留模板和设置，取消地点应用并重置建造记录。之后需重新应用模板。', 'Keep templates and settings, remove location assignments, and reset construction records. Reassign templates afterward.'),
        'eu5ab_deep_decision': ('重新规划本月全国建造', "Replan This Month's Construction"),
        'eu5ab_deep_decision_desc': ('重新评估全国使用已启用模板的地点，保存本月计划，23 日起安排开工。', "Reassess owned locations using enabled templates, save this month's plan, and arrange construction from the 23rd."),
        'eu5ab_open_confirmation': ('打开确认事件', 'Open confirmation'),
        'eu5ab_reset_confirm': ('确认重置', 'Confirm Reset'),
        'eu5ab_reset_confirm_desc': ('保留模板和设置，取消地点应用，并重置计划、等待间隔、报告、总督建议及在建和年度支出记录。已花费金币不退还，已有工程继续施工；需重新应用模板。\\n若刚切换国家，用切换前保存的模板和设置替换当前国家的对应设置。', "Keep templates and settings, but clear location assignments, plans, waiting periods, reports, recommendations, and project and annual spending records. Spent gold is not refunded; existing construction continues. Reassign templates afterward.\\nAfter switching countries, replace this country's templates and settings with those saved before the switch."),
        'eu5ab_deep_confirm_desc': ('重新检查全国使用已启用模板的地点，替换本月未执行的计划。采用当前策略、食物紧急保障和建造顺序，最后一项可超出剩余预算。\\n领土较多时可能需要等待，完成前窗口无法关闭。保存后，本月设置变化不再影响这份计划；23 日起安排开工，次月恢复通常检查。', "Recheck owned locations using enabled templates and replace this month's unexecuted plan. Use the current strategy, food safeguards, and build order; the final project may exceed the remaining budget.\\nLarge countries may take time; the window cannot close until planning finishes. Later settings changes will not alter this plan. Arrange construction from the 23rd; resume regular checks next month."),
        'eu5ab_decision_continue': ('继续，开始计算', 'Continue and calculate'),
        'eu5ab_decision_cancel': ('取消', 'Cancel'),
        'eu5ab_decision_done': ('完成', 'Done'),
        'eu5ab_deep_event_finish': ('完成', 'Done'),
        'eu5ab_deep_event_cancel': ('取消', 'Cancel'),
        'eu5ab_manual_before_23': ('必须在每月 23 日之前使用（1–22 日）', 'Must be used before the 23rd (days 1–22)'),
        'eu5ab_manual_not_dispatched': ('本月尚未开始安排工程开工', "This month's construction orders have not begun"),
        'eu5ab_manual_waiting': ('正在制定本月建造计划，请稍候。完成后即可关闭此窗口。', "Preparing this month's construction plan. Please wait; you can close this window when it is ready."),
        'eu5ab_manual_rgo': ('原产扩建', 'RGO expansion'),
        'eu5ab_manual_expired': ('游戏日期已跨月，本次未执行计划已作废。新月份恢复正常调度。', 'The game date moved into a new month. This unexecuted plan has expired; normal scheduling has resumed.'),
        'eu5ab_manual_results': ("本月建造计划已保存。\\n计划工程：[Player.MakeScope.GetVariable('eu5ab_manual_count').GetValue|0] 项\\n预计支出：[Player.MakeScope.GetVariable('eu5ab_manual_cost').GetValue|2]\\n23 日起安排开工；0 项表示没有符合条件的工程。", "This month's plan is saved.\\nPlanned projects: [Player.MakeScope.GetVariable('eu5ab_manual_count').GetValue|0]\\nEstimated spending: [Player.MakeScope.GetVariable('eu5ab_manual_cost').GetValue|2]\\nConstruction is arranged from the 23rd. A count of 0 means no eligible projects."),
    }
    # Native decisions use .title/.desc; confirmation events use the keys above.
    for decision in ('eu5ab_reset_decision', 'eu5ab_deep_decision'):
        entries[f'{decision}.title'] = entries[decision]
        entries[f'{decision}.desc'] = entries[f'{decision}_desc']
    return '\n' + '\n'.join(f' {key}: ' + json.dumps(pair[0 if zh else 1].replace('\\n', '\n'), ensure_ascii=False)
                            for key, pair in entries.items()) + '\n'


def apply(files, root, settings, presets, catalog_count, replace):
    paths = {k: root / 'in_game/common' / k / ('eu5ab_' + k + '.txt')
             for k in ('scripted_effects', 'scripted_triggers', 'script_values', 'scripted_guis')}
    effects, triggers, values, guis = (files[paths[k]] for k in paths)
    runtime_settings = tuple(s for s in settings if 'governor' not in s and s != 'performance_preset')
    all_config = state.profile_fields(runtime_settings, presets)
    config = (tuple(n for n in all_config[0] if not re.search(r'eu5ab_tpl_\d+_(?:exists|saved|name_id|name_selected|custom_name|building_priorities_initialized)$', n)),
              ('eu5ab_candidate_priority_features',), all_config[2])
    original_storage = state.inventory(effects + guis)
    snapshots = tuple(tuple(n for n in names if n.startswith(('eu5ab_batch_', 'eu5ab_quote_', 'eu5ab_q_quote_'))
                            and not n.endswith(('_sequence', '_serial'))) for names in original_storage)

    # Effective numeric settings apply to engine readers, not CMM/editor writes.
    values = freeze_values(values, config, replace)
    excluded = {key: _block(effects, key) for key in re.findall(r'(?m)^(eu5ab_\w+) = \{', effects)
                if key.startswith(('eu5ab_sync_', 'eu5ab_initialize_', 'eu5ab_apply_performance_', 'eu5ab_rebuild_candidate_priority'))}
    names = ['eu5ab_monthly_build_hard_cap' if s == 'monthly_build_hard_cap' else 'eu5ab_global_' + s
             for s in runtime_settings]
    names += ['eu5ab_candidate_priority_' + s for s in ('upgrade', 'expand', 'rgo', 'new')]
    pattern = r'var:(' + '|'.join(names) + r')\b'
    getter = lambda match: 'eu5ab_manual_value_' + match[1].removeprefix('eu5ab_')
    effects = re.sub(pattern, getter, effects)
    triggers = re.sub(pattern, getter, triggers)
    for name, old in excluded.items():
        effects = replace(effects, name, old)
    # Binding and template membership are part of the saved calculation too.
    for slot in range(1, 21):
        name = f'eu5ab_template_slot_{slot}_building_allowed'
        old = _block(triggers, name)
        frozen = old.replace(f'eu5ab_tpl_{slot}_building_priorities', PREFIX + f'eu5ab_tpl_{slot}_building_priorities')
        triggers = replace(triggers, name, f'''{name} = {{ OR = {{
            AND = {{ {L}.owner = {{ eu5ab_manual_month_current = yes }} {name}_manual = yes }}
            AND = {{ {L}.owner = {{ NOT = {{ eu5ab_manual_month_current = yes }} }} {name}_live = yes }} }} }}''')
        triggers += '\n' + old.replace(name + ' =', name + '_live =', 1) + '\n' + frozen.replace(name + ' =', name + '_manual =', 1)
    name = 'eu5ab_location_template_not_paused'
    old = _block(triggers, name)
    frozen = re.sub(r'has_variable = (eu5ab_(?:tpl_\d+|preset_\w+)_paused)', r'has_variable = ' + PREFIX + r'\1', old)
    triggers = replace(triggers, name, f'''{name} = {{ OR = {{
        AND = {{ owner = {{ eu5ab_manual_month_current = yes }} {name}_manual = yes }}
        AND = {{ owner = {{ NOT = {{ eu5ab_manual_month_current = yes }} }} {name}_live = yes }} }} }}''')
    triggers += '\n' + old.replace(name + ' =', name + '_live =', 1) + '\n' + frozen.replace(name + ' =', name + '_manual =', 1)
    for field, getter_name in (('policy_id', 'policy'), ('template_slot', 'slot')):
        pattern = r'var:eu5ab_' + field + r'\b'
        replacement = 'eu5ab_manual_' + getter_name + '_value'
        triggers = re.sub(pattern, replacement, triggers)
        for key in re.findall(r'(?m)^(eu5ab_(?:try_construct|collect_current|stage_current|prepare_current)\w*) = \{', effects):
            old = _block(effects, key)
            if 'var:eu5ab_' + field in old:
                effects = replace(effects, key, re.sub(pattern, replacement, old))
    # Freeze annual allowance but continue charging real native expenditure.
    limit_body = body(values, 'eu5ab_global_budget_limit_value')
    values = replace(values, 'eu5ab_global_budget_limit_value', f'''eu5ab_global_budget_limit_value = {{ value = 0
        if = {{ limit = {{ eu5ab_manual_month_current = yes }}
            if = {{ limit = {{ has_variable = eu5ab_manual_budget_limit }} add = var:eu5ab_manual_budget_limit }} }}
        else = {{ {limit_body} }} }}''')

    # The ordinary date gate remains authoritative for physical orders.
    # Planning opens read-only queue stages through a separate trigger.
    queue = _block(triggers, 'eu5ab_queue_calendar_open')
    triggers += '\n' + queue.replace('eu5ab_queue_calendar_open =', 'eu5ab_manual_physical_calendar =', 1)
    triggers = replace(triggers, 'eu5ab_queue_calendar_open', '''eu5ab_queue_calendar_open = { OR = {
        eu5ab_manual_physical_calendar = yes
        AND = { has_variable = eu5ab_manual_computing eu5ab_manual_month_current = yes }
    } }''')
    for name, remember in (('eu5ab_batch_issue', 'eu5ab_manual_remember_buildings'), ('eu5ab_batch_rgo_issue', 'eu5ab_manual_remember_rgos')):
        original = _block(effects, name)
        live = original.replace(name + ' =', name + '_live =', 1)
        # Even an unexpected or stale call to the live constructor cannot fire early.
        approved = 'eu5ab_batch_rgo_approved' if 'rgo' in name else 'eu5ab_batch_approved'
        live = name + '_live = { if = { limit = { eu5ab_manual_physical_calendar = yes }' + f'''
            if = {{ limit = {{ has_variable_list = {approved} }} set_variable = eu5ab_manual_dispatch_started }}
            ''' + body(live, name + '_live') + '} }'
        effects = replace(effects, name, f'''{name} = {{
            if = {{ limit = {{ has_variable = eu5ab_manual_computing }} {remember} = yes }}
            else = {{ {name}_live = yes }} }}''') + '\n' + live
    name = 'eu5ab_finish_engine_candidate_queue'
    live = _block(effects, name).replace(name + ' =', name + '_live =', 1)
    effects = replace(effects, name, f'''{name} = {{
        if = {{ limit = {{ has_variable = eu5ab_manual_computing has_variable = eu5ab_manual_sampling has_variable = eu5ab_q_active }}
            remove_variable = eu5ab_manual_sampling
            set_variable = {{ name = eu5ab_q_phase value = 1 }}
            remove_variable = eu5ab_batch_phase remove_variable = eu5ab_batch_rgo_phase remove_variable = eu5ab_batch_rgo_done_phase
            clear_variable_list = eu5ab_batch_pool
            eu5ab_prepare_engine_priority_phase = yes
        }}
        else_if = {{ limit = {{ has_variable = eu5ab_manual_computing }} eu5ab_manual_finish = yes }}
        else = {{ {name}_live = yes }} }}''') + '\n' + live

    # Exhaustive scan bypasses the daily dispatcher entirely. Reset its optional
    # additions cap before the ordinary initializer derives the project quota.
    name = 'eu5ab_run_regional_development_policy'
    old = _block(effects, name)
    old = old.replace(name + ' = {', name + ''' = {
    if = { limit = { NOT = { eu5ab_manual_month_current = yes } } remove_variable = eu5ab_manual_dispatch_started }''', 1)
    marker = 'clamp_variable = { name = eu5ab_scan_max_additions min = 0 max = 600 }'
    if marker not in old: raise ValueError('Missing scan performance boundary')
    old = old.replace(marker, marker + '''
    if = { limit = { has_variable = eu5ab_manual_computing }
        set_variable = { name = eu5ab_scan_max_additions value = 0 }
        set_variable = { name = eu5ab_scan_early_stop value = 0 }
        set_variable = { name = eu5ab_scan_parallel value = 1 } }''')
    effects = replace(effects, name, old)
    name = 'eu5ab_batch_prepare_phase'
    old = _block(effects, name)
    marker = re.search(r'\s*switch = \{\s*trigger = var:eu5ab_q_phase', old[old.index('eu5ab_batch_type_limit'):])
    offset = old.index('eu5ab_batch_type_limit') + marker.start()
    old = old[:offset] + f'''\nif = {{ limit = {{ has_variable = eu5ab_manual_computing }}
        set_variable = {{ name = eu5ab_batch_type_limit value = {catalog_count} }} }}\n''' + old[offset:]
    effects = replace(effects, name, old)

    # Sample every phase before approving anything. Then use the same priority
    # sequence and greedy ranking against shared slots/material/output holds.
    name = 'eu5ab_dispatch_construction_batch'
    old = re.sub(r'\s+', ' ', _block(effects, name))
    stop = 'OR = { eu5ab_global_budget_remaining_value <= 0 var:eu5ab_constructions_started_this_tick >= var:eu5ab_monthly_build_quota }'
    if stop not in old: raise ValueError('Missing batch termination boundary')
    old = old.replace(stop, f'''NOT = {{ has_variable = eu5ab_manual_sampling }}
        OR = {{ {stop} AND = {{ has_variable = eu5ab_manual_computing OR = {{
            eu5ab_batch_planned_value >= eu5ab_global_budget_remaining_value
            eu5ab_batch_reserved_value >= var:eu5ab_monthly_build_quota }} }} }}''')
    old = old.replace('eu5ab_batch_approve = yes eu5ab_batch_issue = yes', '''if = { limit = { has_variable = eu5ab_manual_sampling }
        clear_variable_list = eu5ab_batch_pool }
        else = { eu5ab_batch_approve = yes eu5ab_batch_issue = yes }''')
    effects = replace(effects, name, old)
    effects = wrap(effects, 'eu5ab_batch_rgo_run', 'NOT = { has_variable = eu5ab_manual_sampling }', replace,
                   ' else = { set_variable = { name = eu5ab_batch_rgo_done_phase value = var:eu5ab_q_phase } }')
    name = 'eu5ab_advance_engine_priority_phase'
    old = _block(effects, name).replace('var:eu5ab_constructions_started_this_tick < { value = var:eu5ab_monthly_build_quota }',
        'OR = { has_variable = eu5ab_manual_sampling var:eu5ab_constructions_started_this_tick < { value = var:eu5ab_monthly_build_quota } }')
    effects = replace(effects, name, old)
    # The final overspending item is permitted after any earlier planned items.
    for name in ('eu5ab_batch_approve', 'eu5ab_batch_rgo_approve'):
        old = re.sub(r'\s+', ' ', _block(effects, name))
        old = old.replace('eu5ab_batch_reserved_value = 0', 'OR = { has_variable = eu5ab_manual_computing eu5ab_batch_reserved_value = 0 }')
        effects = replace(effects, name, old)
    # Physical confirmation must not add projects beyond the frozen plan.
    name = 'eu5ab_batch_confirm'
    old = _block(effects, name).replace('NOT = {\n                has_variable = eu5ab_batch_closing\n            }',
        'NOT = { has_variable = eu5ab_batch_closing } NOT = { eu5ab_manual_month_current = yes }')
    # Generated indentation varies after lowering; inject at the unique successor.
    old = re.sub(r'(limit\s*=\s*\{)(\s*has_variable\s*=\s*eu5ab_q_active)', r'\1 NOT = { eu5ab_manual_month_current = yes }\2', old)
    effects = replace(effects, name, old)
    for name in ('eu5ab_settle_scan_candidate_batch', 'eu5ab_refill_regional_development_scan', 'eu5ab_scan_initial_tail', 'eu5ab_scan_regional_development_bucket'):
        effects = wrap(effects, name, 'NOT = { eu5ab_manual_month_current = yes }', replace)

    effects += render_core(config, snapshots)
    name = 'eu5ab_register_location_for_scan'
    old = _block(effects, name).replace(name + ' = {', name + ' = {\n eu5ab_profile_remember_location = yes', 1)
    effects = replace(effects, name, old)
    triggers += '\n' + render_triggers()
    guis += '\n' + render_guis()
    # Profile clearing inventories the complete new runtime, not a stale list.
    effects += state.render_profile(state.inventory(effects + guis), settings, presets)
    files[paths['scripted_effects']] = effects
    files[paths['scripted_triggers']] = triggers
    files[paths['script_values']] = values
    files[paths['scripted_guis']] = guis
    files[root / 'in_game/common/decisions/eu5ab_decisions.txt'] = render_decisions()
    # Overwrite the previous action definitions so upgrades leave no duplicate rows.
    files[root / 'in_game/common/generic_actions/eu5ab_manual_decisions.txt'] = LEGACY_ACTIONS
    files[root / 'in_game/events/eu5ab_decision_events.txt'] = render_events()
    files[root / 'in_game/gui/eventwindow.gui'] = render_event_window()
    files[root / 'in_game/gui/decisions_lateralview.gui'] = render_decisions_window()

    actions_path = root / 'in_game/common/on_action/eu5ab_on_actions.txt'
    actions = files[actions_path]
    name = 'eu5ab_on_cmf_country_transfer'
    old = _block(actions, name).replace('effect = {', 'effect = {\n eu5ab_profile_transfer = yes', 1)
    actions = replace(actions, name, old)
    name = 'eu5ab_on_cmf_after_load'
    old = _block(actions, name)
    pos = old.index('effect = {') + len('effect = {')
    old = old[:pos] + '''
        if = { limit = { eu5ab_manual_month_current = yes } eu5ab_manual_recover = yes }
        else = {''' + old[pos:]
    old = old.rstrip()[:-1] + '}\n}'
    actions = replace(actions, name, old)
    name = 'eu5ab_monthly_country_policy_pulse'
    old = _block(actions, name).replace('effect = {', 'effect = {\n eu5ab_manual_expire = yes', 1)
    actions = replace(actions, name, old)
    files[actions_path] = actions
    monthly_path = root / 'in_game/events/eu5ab_monthly_events.txt'
    monthly = files[monthly_path]
    for name in ('eu5ab_monthly.1', 'eu5ab_monthly.2', 'eu5ab_monthly.3'):
        old = _block(monthly, name)
        pos = old.index('immediate = {') + len('immediate = {')
        old = old[:pos] + '\n eu5ab_manual_expire = yes\n if = { limit = { NOT = { eu5ab_manual_month_current = yes } }' + old[pos:]
        old = old.rstrip()[:-1] + '}\n}'
        monthly = replace(monthly, name, old)
    files[monthly_path] = monthly
    for language in ('simp_chinese', 'english'):
        for layer in ('in_game', 'main_menu'):
            files[root / layer / 'localization' / language / f'eu5ab_l_{language}.yml'] += localization(language)
