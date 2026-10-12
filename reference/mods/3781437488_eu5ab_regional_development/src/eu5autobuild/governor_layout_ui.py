"""Complete-layout pagination, worker GUI, and bilingual UI strings."""
from __future__ import annotations
from .governor_layout_preview import render_preview_panel
from .governor_planner import LOCAL_PLANNER, NAVAL_PLANNER, PlannerType


def _value(name, precision=0):
    return f"[GetPlayer.MakeScope.GetVariable('eu5ab_layout_{name}').GetValue|{precision}]"


LAYOUT_SIMP_CHINESE = {
    "eu5ab_layout_title": "地方治所布局",
    "eu5ab_layout_keep": "暂无达到门槛的迁移建议。",
    "eu5ab_layout_proposal": "有可行的整体布局调整方案。",
    "eu5ab_layout_proposal_single": "有可行的单处治所迁移方案。",
    "eu5ab_layout_summary": f"{_value('result_count')} 处治所；全国布局评分 {_value('result_before', 1)} → {_value('result_after', 1)}，提升 {_value('result_net', 1)}。",
    "eu5ab_layout_progress": f"已比较 {_value('single_candidates')} 个迁移地点。",
    "eu5ab_layout_failed": "刷新未完成，请重试。",
    "eu5ab_layout_page": f"第 {_value('page_number')} / {_value('page_count')} 页",
    "eu5ab_layout_previous": "上一页",
    "eu5ab_layout_next": "下一页",
    "eu5ab_layout_new_sites": "新建选址",
    "eu5ab_layout_show_plan": "治所调整方案",
    "eu5ab_layout_show_plan_tt": "查看哪些治所保留原址、哪些建议迁移。",
    "eu5ab_layout_retained": "保留原址",
    "eu5ab_layout_row_note": "建议迁移至此处。",
    "eu5ab_governor_refresh_button_tt": "立即刷新地方总督治所相关数据。大型帝国重新计算时可能出现短暂卡顿。",
    "eu5ab_regional_development__governor_refresh_now_desc": "立即刷新地方总督治所相关数据。大型帝国重新计算时可能出现短暂卡顿。",
    "eu5ab_governor_migration_threshold": "地方治所迁移收益门槛：[GetPlayer.MakeScope.GetVariable('eu5ab_global_governor_migration_threshold_percent').GetValue|0]%。",
    "eu5ab_local_governor_relocation_alert_tooltip": "有可行的地方治所迁移方案。点击查看详情。",
    "eu5ab_governor_local_status_1": "治所名额已满。",
    "eu5ab_governor_local_status_2": "有空闲名额，暂无合适地点。",
    "eu5ab_governor_local_status_3": "暂无值得新建的地点。",
    "eu5ab_governor_local_status_4": "刷新未完成，请重试。",
    "eu5ab_governor_local_status_6": "当前没有治所名额。",
    "eu5ab_naval_governor_relocation_alert_tooltip": "有可行的海军治所迁移方案。点击查看详情。",
    "eu5ab_layout_candidates_title": "地方治所迁移候选",
    "eu5ab_layout_show_candidates": "迁移候选",
    "eu5ab_layout_candidates_help": f"按预计收益列出前三个地点，包含未达门槛的候选。本次门槛：{_value('result_threshold_percent')}%。",
    "eu5ab_layout_candidates_empty": "暂无可比较的迁移地点。",
    "eu5ab_layout_candidate_pass": "达到门槛",  # nosec B105: UI status text
    "eu5ab_layout_candidate_fail": "未达门槛",
    "eu5ab_layout_candidate_zero_base": "原址贡献为零，不计算提升比例。",
}
LAYOUT_ENGLISH = {
    "eu5ab_layout_title": "Local Seat Layout",
    "eu5ab_layout_keep": "Keep current layout: replanning did not meet the relocation threshold.",
    "eu5ab_layout_proposal": "A worthwhile full-layout relocation plan is available.",
    "eu5ab_layout_proposal_single": "A worthwhile single-seat relocation is available.",
    "eu5ab_layout_summary": f"{_value('result_count')} seats; national layout score {_value('result_before', 1)} → {_value('result_after', 1)}; gain {_value('result_net', 1)}.",
    "eu5ab_layout_progress": f"Relocation sites compared: {_value('single_candidates')}.",
    "eu5ab_layout_failed": "Refresh incomplete. Please try again.",
    "eu5ab_layout_page": f"Page {_value('page_number')} / {_value('page_count')}",
    "eu5ab_layout_previous": "Previous",
    "eu5ab_layout_next": "Next",
    "eu5ab_layout_new_sites": "Available-slot sites",
    "eu5ab_layout_show_plan": "Seat Adjustment Plan",
    "eu5ab_layout_show_plan_tt": "See which seats stay in place and which are recommended for relocation.",
    "eu5ab_layout_retained": "Retain current seat",
    "eu5ab_layout_row_note": "Relocation to this site is recommended.",
    "eu5ab_governor_refresh_button_tt": "Refresh Local Governor seat data now. Recalculating for a large empire may briefly freeze the game.",
    "eu5ab_regional_development__governor_refresh_now_desc": "Refresh Local Governor seat data now. Recalculating for a large empire may briefly freeze the game.",
    "eu5ab_governor_migration_threshold": "Local seat relocation gain threshold: [GetPlayer.MakeScope.GetVariable('eu5ab_global_governor_migration_threshold_percent').GetValue|0]%.",
    "eu5ab_local_governor_relocation_alert_tooltip": "A worthwhile Local Governor relocation is available. Click for details.",
    "eu5ab_governor_local_status_1": "All seat slots are occupied.",
    "eu5ab_governor_local_status_2": "A slot is free, but no suitable site is available.",
    "eu5ab_governor_local_status_3": "No worthwhile new site is available.",
    "eu5ab_governor_local_status_4": "Refresh incomplete. Please try again.",
    "eu5ab_governor_local_status_6": "No seat slots are currently available.",
    "eu5ab_naval_governor_relocation_alert_tooltip": "A worthwhile Naval Governor relocation is available. Click for details.",
    "eu5ab_layout_candidates_title": "Local Relocation Candidates",
    "eu5ab_layout_show_candidates": "Relocation candidates",
    "eu5ab_layout_candidates_help": f"Top three sites by estimated gain, including those below the threshold. This result uses {_value('result_threshold_percent')}%.",
    "eu5ab_layout_candidates_empty": "No relocation sites to compare.",
    "eu5ab_layout_candidate_pass": "Meets threshold",  # nosec B105: UI status text
    "eu5ab_layout_candidate_fail": "Below threshold",
    "eu5ab_layout_candidate_zero_base": "The original seat contributes zero; no percentage is calculated.",
}
for rank in range(1, 4):
    prefix = f"eu5ab_layout_view_{rank}"
    order = f"[GetPlayer.MakeScope.GetVariable('{prefix}_order').GetValue|0]"
    origin = f"[GetPlayer.MakeScope.GetVariable('{prefix}_from').GetLocation.GetName]"
    destination = f"[GetPlayer.MakeScope.GetVariable('{prefix}_to').GetLocation.GetName]"
    LAYOUT_SIMP_CHINESE[f"eu5ab_layout_row_{rank}"] = f"第 {order} 项：{origin} → {destination}"
    LAYOUT_ENGLISH[f"eu5ab_layout_row_{rank}"] = f"{order}. {origin} → {destination}"
    LAYOUT_SIMP_CHINESE[f"eu5ab_layout_row_{rank}_retained"] = f"第 {order} 项：{origin}"
    LAYOUT_ENGLISH[f"eu5ab_layout_row_{rank}_retained"] = f"{order}. {origin}"
    p = f"candidate_{rank}"
    origin = f"[GetPlayer.MakeScope.GetVariable('eu5ab_layout_{p}_from').GetLocation.GetName]"
    destination = f"[GetPlayer.MakeScope.GetVariable('eu5ab_layout_{p}_to').GetLocation.GetName]"
    for catalog in (LAYOUT_SIMP_CHINESE, LAYOUT_ENGLISH):
        catalog[f"eu5ab_layout_candidate_{rank}_title"] = f"{rank}. {origin} → {destination}"
    LAYOUT_SIMP_CHINESE[f"eu5ab_layout_candidate_{rank}_score"] = f"单处治所贡献：{_value(p+'_before', 1)} → {_value(p+'_after', 1)}；提升：{_value(p+'_net', 1)}"
    LAYOUT_ENGLISH[f"eu5ab_layout_candidate_{rank}_score"] = f"Single-seat contribution: {_value(p+'_before', 1)} → {_value(p+'_after', 1)}; gain: {_value(p+'_net', 1)}"
    LAYOUT_SIMP_CHINESE[f"eu5ab_layout_candidate_{rank}_percent"] = f"提升比例：{_value(p+'_percent', 2)}%"
    LAYOUT_ENGLISH[f"eu5ab_layout_candidate_{rank}_percent"] = f"Gain: {_value(p+'_percent', 2)}%"


def render_layout_page_effect() -> str:
    lines = ["eu5ab_layout_refresh_page = {",
             "    set_variable = { name = eu5ab_layout_page_count value = { value = var:eu5ab_layout_result_count divide = 3 ceiling = yes min = 1 } }",
             "    set_variable = { name = eu5ab_layout_page value = { value = var:eu5ab_layout_page min = 0 max = { value = var:eu5ab_layout_page_count subtract = 1 } } }",
             "    set_variable = { name = eu5ab_layout_page_number value = { value = var:eu5ab_layout_page add = 1 } }"]
    for rank in range(1, 4):
        p = f"eu5ab_layout_view_{rank}"
        lines += [f"    clear_variable_list = {p}_list", f"    remove_variable = {p}_retained"]
        for suffix in ("from", "to", "order"):
            lines.append(f"    remove_variable = {p}_{suffix}")
        # Equality with a block enters a scope; calculate before the trigger.
        lines += [f"    set_local_variable = {{ name = eu5ab_layout_page_row value = {{ value = var:eu5ab_layout_page multiply = 3 add = {rank} }} }}",
                  "    every_owned_location = {",
                  "        limit = { has_variable = eu5ab_layout_row_order var:eu5ab_layout_row_order = local_var:eu5ab_layout_page_row }",
                  "        save_temporary_scope_as = eu5ab_layout_page_origin",
                  "        root = {",
                  f"            set_variable = {{ name = {p}_from value = scope:eu5ab_layout_page_origin }}",
                  f"            set_variable = {{ name = {p}_to value = prev.var:eu5ab_layout_row_to }}",
                  f"            set_variable = {{ name = {p}_order value = prev.var:eu5ab_layout_row_order }}",
                  f"            add_to_variable_list = {{ name = {p}_list target = prev.var:eu5ab_layout_row_to }}",
                  f"            if = {{ limit = {{ var:{p}_from = var:{p}_to }} set_variable = {p}_retained }}",
                  "        }", "    }", "    remove_local_variable = eu5ab_layout_page_row"]
    return "\n".join(lines + ["}", ""])


def render_layout_scripted_guis(planner: PlannerType = LOCAL_PLANNER) -> str:
    text = '''eu5ab_gui_layout_tick = {
    scope = country
    is_shown = { is_human = yes has_variable = eu5ab_governor_scan_active }
    is_valid = { is_human = yes has_variable = eu5ab_governor_scan_active }
    effect = { eu5ab_governor_ensure_planner_schema = yes eu5ab_layout_tick = yes }
}
eu5ab_gui_layout_toggle = {
    scope = country
    is_shown = { has_variable = eu5ab_layout_has_results }
    is_valid = { has_variable = eu5ab_layout_has_results }
    effect = {
        remove_variable = eu5ab_layout_show_candidates
        if = { limit = { has_variable = eu5ab_layout_show_new } remove_variable = eu5ab_layout_show_new }
        else = { set_variable = eu5ab_layout_show_new }
    }
}
eu5ab_gui_layout_check_liveness = {
    scope = country
    is_shown = { is_human = yes has_variable = eu5ab_governor_scan_active }
    is_valid = { is_human = yes has_variable = eu5ab_governor_scan_active }
    effect = { eu5ab_layout_check_liveness = yes }
}
'''
    for tab in ("candidates", "new", "plan"):
        action = f"set_variable = eu5ab_layout_show_{tab}" if tab != "plan" else ""
        text += f'''eu5ab_gui_layout_show_{tab} = {{
    scope = country
    is_shown = {{ has_variable = eu5ab_layout_has_results }}
    is_valid = {{ has_variable = eu5ab_layout_has_results }}
    effect = {{
        remove_variable = eu5ab_layout_show_new
        remove_variable = eu5ab_layout_show_candidates
        {action}
    }}
}}
'''
    for direction, comparison, action in (("previous", "> 0", "subtract"), ("next", "< { value = var:eu5ab_layout_page_count subtract = 1 }", "add")):
        text += f'''eu5ab_gui_layout_{direction} = {{
    scope = country
    is_shown = {{ has_variable = eu5ab_layout_has_results }}
    is_valid = {{ var:eu5ab_layout_page {comparison} }}
    effect = {{ change_variable = {{ name = eu5ab_layout_page {action} = 1 }} eu5ab_layout_refresh_page = yes }}
}}
'''
    text = text.replace("is_shown = { has_variable = eu5ab_layout_has_results }", "is_shown = { OR = { has_variable = eu5ab_layout_has_results has_variable = eu5ab_layout_ready } }")
    text = text.replace("is_valid = { has_variable = eu5ab_layout_has_results }", "is_valid = { OR = { has_variable = eu5ab_layout_has_results has_variable = eu5ab_layout_ready } }")
    return planner.bind(text)


def render_layout_worker_gui(planner: PlannerType | None = None) -> str:
    # scripted_widgets registers one root from this file. Both planners' timers
    # must be children of that root to run without daily watchdog fallbacks.
    planners = (LOCAL_PLANNER, NAVAL_PLANNER) if planner is None else (planner,)
    name = (planner or LOCAL_PLANNER).bind("eu5ab_governor_worker")
    timers = "".join(_render_layout_worker_timers(kind) for kind in planners)
    return f'''# Persistent GUI worker: independent of the details window and game date.
widget = {{
    name = "{name}"
    # Instantiate the persistent root even before a player country is available.
    visible = "[EqualTo_CFixedPoint('(CFixedPoint)0', '(CFixedPoint)0')]"
    size = {{ 0 0 }}
{timers}}}
'''


def _render_layout_worker_timers(planner: PlannerType) -> str:
    return planner.bind('''    widget = {
        size = { 0 0 }
        # Keep the timer alive between requests. A manual restart can clear/set
        # scan_active within one frame, so it must not require a visibility edge.
        visible_at_creation = no
        visible = "[GetPlayer.Exists]"
        # EU5 discards duration-only states as having no valid properties.
        # Alpha animates a zero-size widget; it never changes the visible UI.
        state = { name = _show alpha = 1 duration = 0.1 next = eu5ab_layout_pulse }
        state = {
            name = eu5ab_layout_init
            trigger_on_create = yes
            alpha = 1
            duration = 0.1
            next = eu5ab_layout_pulse
        }
        state = {
            name = eu5ab_layout_pulse
            alpha = 0
            duration = 0.1
            on_finish = "[PdxGuiTriggerAllAnimations('eu5ab_layout_pulse_send')]"
            next = eu5ab_layout_pulse_wait
        }
        state = { name = eu5ab_layout_pulse_wait alpha = 1 duration = 0.1 next = eu5ab_layout_pulse }
        # Keep the controller alive for immediate manual restarts, but only
        # instantiate a command sender while the server accepts this request.
        widget = {
            datamodel = "[DataModelRepeatedItem(Select_int32(And(GetPlayer.Exists, GetScriptedGui('eu5ab_gui_layout_tick').IsShown(GuiScope.SetRoot(GetPlayer.MakeScope).End)), '(int32)1', '(int32)0'))]"
            item = { widget = {
                state = { name = _show alpha = 1 }
                state = { name = eu5ab_layout_pulse_send alpha = 0 duration = 0.01
                    on_finish = "[GetScriptedGui('eu5ab_gui_layout_tick').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
                    next = eu5ab_layout_pulse_send_wait }
                state = { name = eu5ab_layout_pulse_send_wait alpha = 1 duration = 0.01 }
            } }
        }
    }
    # Separate timer: detect a stopped pulse chain even while the game is paused.
    widget = {
        size = { 0 0 }
        visible_at_creation = no
        visible = "[GetPlayer.Exists]"
        state = { name = _show alpha = 1 duration = 0.1 next = eu5ab_layout_liveness }
        state = {
            name = eu5ab_layout_liveness_init
            trigger_on_create = yes
            alpha = 1
            duration = 0.1
            next = eu5ab_layout_liveness
        }
        state = {
            name = eu5ab_layout_liveness
            alpha = 0
            duration = 5
            on_finish = "[PdxGuiTriggerAllAnimations('eu5ab_layout_liveness_send')]"
            next = eu5ab_layout_liveness_wait
        }
        state = { name = eu5ab_layout_liveness_wait alpha = 1 duration = 0.1 next = eu5ab_layout_liveness }
        widget = {
            datamodel = "[DataModelRepeatedItem(Select_int32(And(GetPlayer.Exists, GetScriptedGui('eu5ab_gui_layout_check_liveness').IsShown(GuiScope.SetRoot(GetPlayer.MakeScope).End)), '(int32)1', '(int32)0'))]"
            item = { widget = {
                state = { name = _show alpha = 1 }
                state = { name = eu5ab_layout_liveness_send alpha = 0 duration = 0.01
                    on_finish = "[GetScriptedGui('eu5ab_gui_layout_check_liveness').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
                    next = eu5ab_layout_liveness_send_wait }
                state = { name = eu5ab_layout_liveness_send_wait alpha = 1 duration = 0.01 }
            } }
        }
    }
''')


def render_layout_panel(legacy: str, planner: PlannerType = LOCAL_PLANNER) -> str:
    has = "Or(GetPlayer.MakeScope.GetVariable('eu5ab_layout_has_results').IsSet, GetPlayer.MakeScope.GetVariable('eu5ab_layout_ready').IsSet)"
    new = "GetPlayer.MakeScope.GetVariable('eu5ab_layout_show_new').IsSet"
    candidates = "GetPlayer.MakeScope.GetVariable('eu5ab_layout_show_candidates').IsSet"
    legacy = legacy.replace('name = "eu5ab_governor_local_panel"',
                            f'name = "eu5ab_governor_local_panel"\n visible = "[Or(Not({has}), And({new}, Not({candidates})))]"')
    legacy = legacy.replace("size = { 524 42 }", "size = { 208 42 }", 1)
    # Both type panels are overlaid children of plain widgets; explicitly fill
    # their containers instead of relying on an outer hbox to stretch them.
    legacy = legacy.replace(
        "\n\t\t\t\tsize = { 544 600 }",
        "\n\t\t\t\tsize = { 100% 100% }",
        1,
    )
    index = legacy.rfind("}")
    legacy = legacy[:index] + f'''button_regular = {{
        position = {{ 396 14 }} size = {{ 138 28 }}
        visible = "[{has}]"
        text = "eu5ab_layout_show_plan"
        tooltip = "eu5ab_layout_show_plan_tt"
        onclick = "[GetScriptedGui('eu5ab_gui_layout_toggle').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
    }}
    button_regular = {{
        position = {{ 252 14 }} size = {{ 138 28 }}
        visible = "[{has}]"
        text = "eu5ab_layout_show_candidates"
        tooltip = "eu5ab_layout_show_candidates"
        onclick = "[GetScriptedGui('eu5ab_gui_layout_show_candidates').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
    }}
''' + legacy[index:]
    cards = []
    for rank in range(1, 4):
        p = f"eu5ab_layout_view_{rank}"
        cards.append(f'''widget = {{
        position = {{ 10 {126 + (rank-1)*128} }} size = {{ 524 120 }}
        datamodel = "[GetPlayer.MakeScope.GetList('{p}_list')]"
        item = {{ widget = {{
            datacontext = "[Scope.GetLocation]"
            size = {{ 524 120 }} using = bg_square_wood_tile using = bg_cabinet_card_frame
            text_multi = {{
                position = {{ 12 10 }} size = {{ 380 44 }}
                autoresize = no fontsize = 17 fontsize_min = 12 default_format = "#yellow_titles"
                visible = "[Not(GetPlayer.MakeScope.GetVariable('{p}_retained').IsSet)]"
                text = "eu5ab_layout_row_{rank}"
            }}
            text_multi = {{
                position = {{ 12 10 }} size = {{ 380 44 }}
                autoresize = no fontsize = 17 fontsize_min = 12 default_format = "#yellow_titles"
                visible = "[GetPlayer.MakeScope.GetVariable('{p}_retained').IsSet]"
                text = "eu5ab_layout_row_{rank}_retained"
            }}
            button_regular = {{
                position = {{ 400 12 }} size = {{ 112 30 }}
                text = "eu5ab_governor_view_location"
                tooltip = "eu5ab_governor_view_location_tt"
                onclick = "[PanToLocation(Location.Self)]"
            }}
            text_single = {{
                position = {{ 12 56 }} size = {{ 490 22 }} fontsize = 14
                visible = "[GetPlayer.MakeScope.GetVariable('{p}_retained').IsSet]"
                text = "eu5ab_layout_retained"
            }}
            text_multi = {{
                position = {{ 12 80 }} size = {{ 490 32 }} fontsize = 12 fontsize_min = 10 autoresize = no
                visible = "[Not(GetPlayer.MakeScope.GetVariable('{p}_retained').IsSet)]"
                text = "eu5ab_layout_row_note"
            }}
        }} }}
    }}''')
    return planner.bind_ui(f'''widget = {{
    name = "eu5ab_layout_local_container"
    layoutpolicy_horizontal = fixed layoutpolicy_vertical = expanding
    size = {{ 544 600 }} minimumsize = {{ 544 600 }} maximumsize = {{ 544 2000 }}
    {legacy}
    {render_preview_panel()}
    widget = {{
        name = "eu5ab_layout_panel"
        visible = "[And({has}, And(Not({new}), Not({candidates})))]"
        size = {{ 100% 100% }} using = bg_secondary_inner_alt
        text_single = {{
            position = {{ 10 10 }} size = {{ 208 42 }} fontsize = 20 fontsize_min = 16 autoresize = no
            align = left|vcenter default_format = "#yellow_titles"
            text = "eu5ab_layout_title"
        }}
        button_regular = {{
            position = {{ 252 14 }} size = {{ 138 28 }} text = "eu5ab_layout_show_candidates"
            tooltip = "eu5ab_layout_show_candidates"
            onclick = "[GetScriptedGui('eu5ab_gui_layout_show_candidates').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
        }}
        button_regular = {{
            position = {{ 396 14 }} size = {{ 138 28 }} text = "eu5ab_layout_new_sites"
            tooltip = "eu5ab_layout_new_sites"
            onclick = "[GetScriptedGui('eu5ab_gui_layout_toggle').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
        }}
        text_multi = {{
            position = {{ 10 50 }} size = {{ 524 30 }} fontsize = 13 fontsize_min = 11 autoresize = no
            visible = "[Not(GetPlayer.MakeScope.GetVariable('eu5ab_layout_result_proposal').IsSet)]"
            text = "eu5ab_layout_keep"
        }}
        text_multi = {{
            position = {{ 10 50 }} size = {{ 524 30 }} fontsize = 13 fontsize_min = 11 autoresize = no
            visible = "[And(GetPlayer.MakeScope.GetVariable('eu5ab_layout_result_proposal').IsSet, Not(EqualTo_CFixedPoint(GetPlayer.MakeScope.GetVariable('eu5ab_layout_result_kind').GetValue, '(CFixedPoint)2')))]"
            text = "eu5ab_layout_proposal"
        }}
        text_multi = {{
            position = {{ 10 50 }} size = {{ 524 30 }} fontsize = 13 fontsize_min = 11 autoresize = no
            visible = "[EqualTo_CFixedPoint(GetPlayer.MakeScope.GetVariable('eu5ab_layout_result_kind').GetValue, '(CFixedPoint)2')]"
            text = "eu5ab_layout_proposal_single"
        }}
        text_multi = {{ position = {{ 10 84 }} size = {{ 524 38 }} fontsize = 13 fontsize_min = 11 autoresize = no text = "eu5ab_layout_summary" tooltip = "eu5ab_governor_road_tier_help" }}
        {' '.join(cards)}
        widget = {{
            name = "eu5ab_layout_pagination"
            parentanchor = bottom|left widgetanchor = bottom|left
            position = {{ 10 -10 }} size = {{ 524 32 }}
            button_regular = {{
                position = {{ 0 0 }} size = {{ 128 32 }} text = "eu5ab_layout_previous"
                tooltip = "eu5ab_layout_previous"
                enabled = "[GetScriptedGui('eu5ab_gui_layout_previous').IsValid(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
                onclick = "[GetScriptedGui('eu5ab_gui_layout_previous').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
            }}
            text_single = {{
                position = {{ 138 0 }} size = {{ 248 32 }} autoresize = no
                align = center|nobaseline fontsize = 14 fontsize_min = 11 text = "eu5ab_layout_page"
            }}
            button_regular = {{
                position = {{ 396 0 }} size = {{ 128 32 }} text = "eu5ab_layout_next"
                tooltip = "eu5ab_layout_next"
                enabled = "[GetScriptedGui('eu5ab_gui_layout_next').IsValid(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
                onclick = "[GetScriptedGui('eu5ab_gui_layout_next').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
            }}
        }}
    }}
}}''')
