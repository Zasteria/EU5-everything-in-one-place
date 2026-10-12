"""Published top-three single-move comparisons, independent of alert eligibility."""
from __future__ import annotations


def render_preview_effects() -> str:
    lines = ["eu5ab_layout_clear_candidates = {",
             "    set_variable = { name = eu5ab_layout_candidate_count value = 0 }",
             "    remove_variable = eu5ab_layout_result_threshold_percent"]
    for rank in range(1, 4):
        prefix = f"eu5ab_layout_candidate_{rank}"
        lines.append(f"    clear_variable_list = {prefix}_list")
        for field in ("from", "to", "before", "after", "net", "percent", "qualifies", "zero_base"):
            lines.append(f"    remove_variable = {prefix}_{field}")
    lines += ["}", "", "eu5ab_layout_publish_candidates = {",
              "    eu5ab_layout_clear_candidates = yes",
              "    set_variable = { name = eu5ab_layout_result_threshold_percent value = var:eu5ab_layout_threshold_percent }",
              "    ordered_owned_location = {",
              "        limit = { has_variable = eu5ab_layout_preview_from eu5ab_local_governor_candidate = yes }",
              "        order_by = var:eu5ab_layout_preview_net", "        max = 3",
              "        check_range_bounds = no",
              "        save_temporary_scope_as = eu5ab_layout_preview_target",
              "        root = {",
              "            change_variable = { name = eu5ab_layout_candidate_count add = 1 }"]
    for rank in range(1, 4):
        p = f"eu5ab_layout_candidate_{rank}"
        lines += ["            if = {",
                  f"                limit = {{ var:eu5ab_layout_candidate_count = {rank} }}",
                  f"                set_variable = {{ name = {p}_from value = prev.var:eu5ab_layout_preview_from }}",
                  f"                set_variable = {{ name = {p}_to value = scope:eu5ab_layout_preview_target }}",
                  f"                add_to_variable_list = {{ name = {p}_list target = scope:eu5ab_layout_preview_target }}",
                  f"                set_variable = {{ name = {p}_before value = prev.var:eu5ab_layout_preview_before }}",
                  f"                set_variable = {{ name = {p}_net value = prev.var:eu5ab_layout_preview_net }}",
                  f"                set_variable = {{ name = {p}_after value = {{ value = var:{p}_before add = var:{p}_net }} }}",
                  "                if = {",
                  f"                    limit = {{ var:{p}_before > 0 }}",
                  f"                    set_variable = {{ name = {p}_percent value = {{ value = var:{p}_net divide = var:{p}_before multiply = 100 }} }}",
                  "                }",
                  f"                else = {{ set_variable = {p}_zero_base }}",
                  "                if = {",
                  f"                    limit = {{ var:{p}_net > 0 var:{p}_net >= {{ value = var:{p}_before multiply = var:eu5ab_layout_threshold_percent divide = 100 }} }}",
                  f"                    set_variable = {p}_qualifies",
                  "                }", "            }"]
    return "\n".join(lines + ["        }", "    }", "}", ""]) + '''
eu5ab_governor_initialize_threshold_setting = {
    if = {
        limit = { NOT = { is_key_in_variable_map = { name = cmm target = flag:eu5ab_regional_development__governor_migration_threshold_percent } } }
        cmm_set_setting_value = { setting = eu5ab_regional_development__governor_migration_threshold_percent value = 80 }
    }
}

# CMM supplies +/-1 and Ctrl +/-5 natively. Shift writes an endpoint before
# the callback; convert only this numeric setting's endpoint to a +/-10 step.
# Normal/Ctrl clicks that reach a bound produce the same clamped result.
# Reset writes 80, not an endpoint, so it is never reinterpreted.
eu5ab_governor_adjust_threshold_step = {
    if = {
        limit = { has_variable = eu5ab_global_governor_migration_threshold_percent }
        if = {
            limit = {
                "variable_map(cmm|flag:eu5ab_regional_development__governor_migration_threshold_percent)" = 200
                var:eu5ab_global_governor_migration_threshold_percent < 200
            }
            set_variable = { name = eu5ab_cmm_threshold_step value = { value = var:eu5ab_global_governor_migration_threshold_percent add = 10 max = 200 } }
            cmm_set_setting_value = { setting = eu5ab_regional_development__governor_migration_threshold_percent value = var:eu5ab_cmm_threshold_step }
        }
        else_if = {
            limit = {
                "variable_map(cmm|flag:eu5ab_regional_development__governor_migration_threshold_percent)" = 0
                var:eu5ab_global_governor_migration_threshold_percent > 0
            }
            set_variable = { name = eu5ab_cmm_threshold_step value = { value = var:eu5ab_global_governor_migration_threshold_percent subtract = 10 min = 0 } }
            cmm_set_setting_value = { setting = eu5ab_regional_development__governor_migration_threshold_percent value = var:eu5ab_cmm_threshold_step }
        }
    }
    remove_variable = eu5ab_cmm_threshold_step
}
'''


def render_preview_panel() -> str:
    cards = []
    for rank in range(1, 4):
        p = f"eu5ab_layout_candidate_{rank}"
        qualified = f"GetPlayer.MakeScope.GetVariable('{p}_qualifies').IsSet"
        zero_base = f"GetPlayer.MakeScope.GetVariable('{p}_zero_base').IsSet"
        cards.append(f'''widget = {{
            name = "{p}_card"
            position = {{ 10 {112 + (rank-1)*152} }} size = {{ 524 144 }}
            datamodel = "[GetPlayer.MakeScope.GetList('{p}_list')]"
            item = {{ widget = {{
                size = {{ 524 144 }} datacontext = "[Scope.GetLocation]"
                using = bg_square_wood_tile using = bg_cabinet_card_frame
                text_multi = {{
                    position = {{ 12 8 }} size = {{ 378 42 }} autoresize = no
                    fontsize = 17 fontsize_min = 12 default_format = "#yellow_titles" text = "{p}_title"
                }}
                button_regular = {{
                    position = {{ 400 12 }} size = {{ 112 30 }}
                    text = "eu5ab_governor_view_location" tooltip = "eu5ab_governor_view_location_tt"
                    onclick = "[PanToLocation(Location.Self)]"
                }}
                text_single = {{
                    position = {{ 12 54 }} size = {{ 496 24 }} fontsize = 14 fontsize_min = 11 autoresize = no
                    text = "{p}_score"
                }}
                text_single = {{
                    position = {{ 12 82 }} size = {{ 496 24 }} fontsize = 14 fontsize_min = 11 autoresize = no
                    visible = "[Not({zero_base})]" text = "{p}_percent"
                }}
                text_single = {{
                    position = {{ 12 82 }} size = {{ 496 24 }} fontsize = 14 fontsize_min = 11 autoresize = no
                    visible = "[{zero_base}]" text = "eu5ab_layout_candidate_zero_base"
                }}
                text_single = {{
                    position = {{ 12 110 }} size = {{ 496 24 }} fontsize = 14
                    visible = "[{qualified}]" text = "eu5ab_layout_candidate_pass"
                }}
                text_single = {{
                    position = {{ 12 110 }} size = {{ 496 24 }} fontsize = 14
                    visible = "[Not({qualified})]" text = "eu5ab_layout_candidate_fail"
                }}
            }} }}
        }}''')
    return f'''widget = {{
        name = "eu5ab_layout_candidates_panel" size = {{ 100% 100% }} using = bg_secondary_inner_alt
        visible = "[And(Or(GetPlayer.MakeScope.GetVariable('eu5ab_layout_has_results').IsSet, GetPlayer.MakeScope.GetVariable('eu5ab_layout_ready').IsSet), GetPlayer.MakeScope.GetVariable('eu5ab_layout_show_candidates').IsSet)]"
        text_single = {{
            position = {{ 10 10 }} size = {{ 208 42 }} fontsize = 20 fontsize_min = 16 autoresize = no
            align = left|vcenter default_format = "#yellow_titles"
            text = "eu5ab_layout_candidates_title"
        }}
        button_regular = {{
            position = {{ 252 14 }} size = {{ 138 28 }} text = "eu5ab_layout_new_sites" tooltip = "eu5ab_layout_new_sites"
            onclick = "[GetScriptedGui('eu5ab_gui_layout_show_new').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
        }}
        button_regular = {{
            position = {{ 396 14 }} size = {{ 138 28 }} text = "eu5ab_layout_show_plan" tooltip = "eu5ab_layout_show_plan_tt"
            onclick = "[GetScriptedGui('eu5ab_gui_layout_show_plan').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
        }}
        text_multi = {{
            position = {{ 10 54 }} size = {{ 524 48 }} fontsize = 14 fontsize_min = 11 autoresize = no
            text = "eu5ab_layout_candidates_help"
        }}
        {' '.join(cards)}
        text_multi = {{
            position = {{ 10 160 }} size = {{ 524 60 }} fontsize = 17 align = center
            visible = "[Not(GetPlayer.MakeScope.GetVariable('eu5ab_layout_candidate_1_to').IsSet)]"
            text = "eu5ab_layout_candidates_empty"
        }}
    }}'''
