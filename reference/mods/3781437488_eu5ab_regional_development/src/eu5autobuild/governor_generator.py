"""Generate the recommendation-only Local and Naval Governor runtime.

The two evaluators deliberately share only bounded graph plumbing and the
location-value model.  Eligibility, region construction, ranking, thresholds,
and migration state are separate so a future vanilla change to one Governor
type cannot silently alter the other.
"""

from __future__ import annotations

from .governor_connections import bundled_straits, render_connection_effects, render_connection_trigger
from .governor_refresh import integrate_refresh, add_footprint_links, render_refresh_triggers
from .governor_transport_generator import (
    render_transport_values, render_transport_effects, render_lake_relaxation,
)
from .governor_layout_generator import render_layout_effects
from .governor_planner import NAVAL_PLANNER, script_definition, render_planner_schema_effects
from .governor_naval import render_naval_effects, render_scheduled_planners
from .governor_layout_ui import (
    LAYOUT_ENGLISH, LAYOUT_SIMP_CHINESE, render_layout_panel,
    render_layout_scripted_guis,
)


GOVERNOR_RECOMMENDATION_BUILDINGS = frozenset(
    {"local_governor", "naval_governor"}
)



def _sync_value(name: str, precision: int = 0) -> str:
    return f"[GetPlayer.MakeScope.GetVariable('eu5ab_gov_sync_{name}').GetValue|{precision}]"


GOVERNOR_SIMP_CHINESE_LOCALIZATION = {
    "eu5ab_regional_development__governors_name": "总督推荐",
    "eu5ab_regional_development__governors__recommendations_name": "推荐与刷新",
    "eu5ab_regional_development__governors__recommendations_desc": "仅分析地方总督治所与海军总督治所的候选地点；系统不会自动建造、拆除或迁移建筑。",
    "eu5ab_regional_development__governors__scoring_name": "评分偏好",
    "eu5ab_regional_development__governors__scoring_desc": "选择地点价值的侧重点，并决定是否把港口、边境与要塞等战略位置纳入评分。",
    "eu5ab_regional_development__governor_recommendations_enabled_name": "启用总督推荐",
    "eu5ab_regional_development__governor_recommendations_enabled_desc": "定期提供地方和海军总督治所选址建议。关闭后保留上次结果，但不再显示推荐提醒。",
    "eu5ab_regional_development__governor_refresh_interval_name": "刷新周期",
    "eu5ab_regional_development__governor_refresh_interval_desc": "设置治所建议的更新间隔。部分领土、首都、地点等级和制度变化会提前触发更新；道路及其他邻近度变化在定期评估时一并考虑。",
    "eu5ab_regional_development__governor_refresh_interval_option_1_name": "每 1 个月",
    "eu5ab_regional_development__governor_refresh_interval_option_1_desc": "最快反映变化，适合小国；大国频繁评估可能造成更明显的停顿。",
    "eu5ab_regional_development__governor_refresh_interval_option_2_name": "每 3 个月",
    "eu5ab_regional_development__governor_refresh_interval_option_2_desc": "在道路变化响应速度与大型国家性能之间取得平衡。",
    "eu5ab_regional_development__governor_refresh_interval_option_3_name": "每 6 个月",
    "eu5ab_regional_development__governor_refresh_interval_option_3_desc": "降低大型国家的周期计算频率。",
    "eu5ab_regional_development__governor_refresh_interval_option_4_name": "每 12 个月",
    "eu5ab_regional_development__governor_refresh_interval_option_4_desc": "开销最低，但道路与邻近度变化最多需要一年才反映到推荐中。",
    "eu5ab_regional_development__governor_refresh_now_name": "立即重新计算",
    "eu5ab_regional_development__governor_refresh_now_text": "立即重新计算",
    "eu5ab_regional_development__governor_refresh_now_desc": "立即执行一次完整计算并更新详情窗口；只有达到价值门槛且推荐发生有意义变化时才显示横幅。",
    "eu5ab_regional_development__governor_scoring_profile_name": "地点价值偏好",
    "eu5ab_regional_development__governor_scoring_profile_desc": "控制地点财富、人口与发展度的相对权重。评分根据地点价值与预计改善的邻近度综合测算，并非最终控制力数值；当前控制力不参与加分或抵扣。",
    "eu5ab_regional_development__governor_scoring_profile_option_1_name": "混合",
    "eu5ab_regional_development__governor_scoring_profile_option_1_desc": "平衡地点财富、人口与发展度。",
    "eu5ab_regional_development__governor_scoring_profile_option_2_name": "经济",
    "eu5ab_regional_development__governor_scoring_profile_option_2_desc": "更重视地点财富与已有经济规模。",
    "eu5ab_regional_development__governor_scoring_profile_option_3_name": "行政人口",
    "eu5ab_regional_development__governor_scoring_profile_option_3_desc": "更重视人口与发展度。",
    "eu5ab_regional_development__governor_strategic_value_name": "计入战略价值",
    "eu5ab_regional_development__governor_strategic_value_desc": "开启后，港口、邻接外国的边境地点和拥有要塞的地点会获得有限加权。该设置只调整地点价值，不作为独立子评分。",
    "eu5ab_governor_window_title": "总督推荐详情",
    "eu5ab_governor_window_intro": "查看治所新建与迁移建议。",
    "eu5ab_governor_road_tier_help": "按已解锁的最高道路等级估算，实际收益可能不同。",
    "eu5ab_governor_refresh_button": "重新计算",
    "eu5ab_governor_refresh_button_tt": "重新评估地方和海军治所的新建、迁移及布局建议。大国可能短暂卡顿，未完成时会显示提示。",
    "eu5ab_governor_local_section": "地方总督治所",
    "eu5ab_governor_local_diagnostics": (
        f"最近一次地方治所计算：阶段 {_sync_value('stage')}，状态 {_sync_value('status')}；"
        f"名额 {_sync_value('capacity')}，引擎统计地方治所 {_sync_value('occupied')}、总督辖区 {_sync_value('lieutenancies')}，其他建筑占用 {_sync_value('other_slots')}。\\n"
        f"逐地重数：地方治所 {_sync_value('fresh_occupied')}、总督辖区 {_sync_value('fresh_lieutenancies')}，其他建筑占用 {_sync_value('fresh_other_slots')}；"
        f"空位判断（引擎/逐地） {_sync_value('slot_available')}/{_sync_value('fresh_slot_available')}，"
        f"不一致 {_sync_value('slot_cache_mismatch')}（1 表示有差异）。\\n"
        f"新建收益门槛 {_sync_value('threshold', 1)}；候选地点 {_sync_value('candidates')}，完成评分 {_sync_value('shortlisted')}。"
    ),
    "eu5ab_governor_naval_section": "海军总督治所",
    "eu5ab_governor_naval_diagnostics": "海军治所最近一次计算：状态 [GetPlayer.MakeScope.GetVariable('eu5ab_naval_gov_sync_status').GetValue|0]；累计刷新 [GetPlayer.MakeScope.GetVariable('eu5ab_naval_gov_sync_runs').GetValue|0] 次。",
    "eu5ab_governor_new_slot_state": "有空闲名额，可在以下地点新建治所。",
    "eu5ab_governor_empty_title": "暂无合适的候选地点",
    "eu5ab_governor_no_recommendation": "#weak 可在领土或城市发展后重新计算。#!",
    "eu5ab_governor_candidate_1": "第 1 名",
    "eu5ab_governor_candidate_2": "第 2 名",
    "eu5ab_governor_candidate_3": "第 3 名",
    "eu5ab_governor_view_location": "查看地点",
    "eu5ab_governor_view_location_tt": "将地图镜头移动到此候选地点。",
    "eu5ab_governor_local_candidate_1_name": "[GetPlayer.MakeScope.GetVariable('eu5ab_local_top_1').GetLocation.GetName]",
    "eu5ab_governor_local_candidate_2_name": "[GetPlayer.MakeScope.GetVariable('eu5ab_local_top_2').GetLocation.GetName]",
    "eu5ab_governor_local_candidate_3_name": "[GetPlayer.MakeScope.GetVariable('eu5ab_local_top_3').GetLocation.GetName]",
    "eu5ab_governor_naval_candidate_1_name": "[GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_1').GetLocation.GetName]",
    "eu5ab_governor_naval_candidate_2_name": "[GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_2').GetLocation.GetName]",
    "eu5ab_governor_naval_candidate_3_name": "[GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_3').GetLocation.GetName]",
    "eu5ab_governor_local_candidate_1_breakdown": "综合评分 [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_1_score').GetValue|1] = 自身邻近度改善收益 [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_1_site_gain').GetValue|1] + 周边地点邻近度改善收益 [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_1_surrounding_gain').GetValue|1]。\\n预计有 [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_1_coverage').GetValue|0] 个地点（含自身）的邻近度将得到改善。\\n评分根据各地点价值乘以预计邻近度提升比例测算，并非最终控制力数值；当前控制力不参与加减分，实际控制力仍会随最大控制力等机制自然演变。",
    "eu5ab_governor_local_candidate_2_breakdown": "综合评分 [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_2_score').GetValue|1] = 自身邻近度改善收益 [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_2_site_gain').GetValue|1] + 周边地点邻近度改善收益 [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_2_surrounding_gain').GetValue|1]。\\n预计有 [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_2_coverage').GetValue|0] 个地点（含自身）的邻近度将得到改善。\\n评分根据各地点价值乘以预计邻近度提升比例测算，并非最终控制力数值；当前控制力不参与加减分，实际控制力仍会随最大控制力等机制自然演变。",
    "eu5ab_governor_local_candidate_3_breakdown": "综合评分 [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_3_score').GetValue|1] = 自身邻近度改善收益 [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_3_site_gain').GetValue|1] + 周边地点邻近度改善收益 [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_3_surrounding_gain').GetValue|1]。\\n预计有 [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_3_coverage').GetValue|0] 个地点（含自身）的邻近度将得到改善。\\n评分根据各地点价值乘以预计邻近度提升比例测算，并非最终控制力数值；当前控制力不参与加减分，实际控制力仍会随最大控制力等机制自然演变。",
    "eu5ab_governor_naval_candidate_1_breakdown": "综合评分 [GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_1_score').GetValue|1] = 自身邻近度改善收益 [GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_1_site_gain').GetValue|1] + 周边地点邻近度改善收益 [GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_1_surrounding_gain').GetValue|1]。",
    "eu5ab_governor_naval_candidate_2_breakdown": "综合评分 [GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_2_score').GetValue|1] = 自身邻近度改善收益 [GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_2_site_gain').GetValue|1] + 周边地点邻近度改善收益 [GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_2_surrounding_gain').GetValue|1]。",
    "eu5ab_governor_naval_candidate_3_breakdown": "综合评分 [GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_3_score').GetValue|1] = 自身邻近度改善收益 [GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_3_site_gain').GetValue|1] + 周边地点邻近度改善收益 [GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_3_surrounding_gain').GetValue|1]。",
    "eu5ab_governor_migration_threshold": "有空闲槽位时会直接显示推荐；迁移建议需连续两次达到至少20%的提升和最低收益门槛，并受 12 个月冷却限制。",
    "eu5ab_governor_bounded_warning": "#warning 部分评估未完成，相关建议暂不显示。#!",
    "eu5ab_local_governor_available_alert_name": "可以新建地方总督治所",
    "eu5ab_local_governor_available_alert_tooltip": "推荐：[GetPlayer.MakeScope.GetVariable('eu5ab_local_top_1').GetLocation.GetName]\\n该地点在最高道路规划下拥有最高的区域邻近度边际收益，已扣除共同的道路升级收益。左键打开详情；右键隐藏；Shift+右键静音。",
    "eu5ab_local_governor_available_alert_icon": "@local_governor!",
    "eu5ab_local_governor_available_alert_color": "green",
    "eu5ab_local_governor_relocation_alert_name": "建议迁移地方总督治所",
    "eu5ab_local_governor_relocation_alert_icon": "@local_governor!",
    "eu5ab_local_governor_relocation_alert_color": "yellow",
    "eu5ab_naval_governor_available_alert_name": "可以新建海军总督治所",
    "eu5ab_naval_governor_available_alert_tooltip": "推荐：[GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_1').GetLocation.GetName]\\n该港口是高价值分离领地中当前最合适的内陆覆盖中心。左键打开详情；右键隐藏；Shift+右键静音。",
    "eu5ab_naval_governor_available_alert_icon": "@naval_governor!",
    "eu5ab_naval_governor_available_alert_color": "blue",
    "eu5ab_naval_governor_relocation_alert_name": "建议迁移海军总督治所",
    "eu5ab_naval_governor_relocation_alert_icon": "@naval_governor!",
    "eu5ab_naval_governor_relocation_alert_color": "blue",
}


GOVERNOR_ENGLISH_LOCALIZATION = {
    "eu5ab_regional_development__governors_name": "Governor Recommendations",
    "eu5ab_regional_development__governors__recommendations_name": "Recommendations & Refresh",
    "eu5ab_regional_development__governors__recommendations_desc": "Analyze Local Governor and Naval Governor candidates without constructing, removing, or relocating buildings.",
    "eu5ab_regional_development__governors__scoring_name": "Scoring Preferences",
    "eu5ab_regional_development__governors__scoring_desc": "Choose how location value is weighted and whether limited strategic value is included.",
    "eu5ab_regional_development__governor_recommendations_enabled_name": "Enable Governor Recommendations",
    "eu5ab_regional_development__governor_recommendations_enabled_desc": "Periodically suggest Local and Naval Governor sites. Disabling keeps the last results but removes recommendation alerts.",
    "eu5ab_regional_development__governor_refresh_interval_name": "Refresh Interval",
    "eu5ab_regional_development__governor_refresh_interval_desc": "Set the update interval. Some territory, capital, location-rank, and government changes prompt earlier updates. Roads and other Proximity changes are included in scheduled checks.",
    "eu5ab_regional_development__governor_refresh_interval_option_1_name": "Every Month",
    "eu5ab_regional_development__governor_refresh_interval_option_1_desc": "Updates most quickly and suits smaller countries. Frequent checks may cause longer pauses in large countries.",
    "eu5ab_regional_development__governor_refresh_interval_option_2_name": "Every 3 Months",
    "eu5ab_regional_development__governor_refresh_interval_option_2_desc": "Balanced road-change response and large-country performance.",
    "eu5ab_regional_development__governor_refresh_interval_option_3_name": "Every 6 Months",
    "eu5ab_regional_development__governor_refresh_interval_option_3_desc": "Lower recalculation frequency for large countries.",
    "eu5ab_regional_development__governor_refresh_interval_option_4_name": "Every 12 Months",
    "eu5ab_regional_development__governor_refresh_interval_option_4_desc": "Lowest cost, but road and proximity changes can take up to a year to appear.",
    "eu5ab_regional_development__governor_refresh_now_name": "Recalculate Now",
    "eu5ab_regional_development__governor_refresh_now_text": "Recalculate Now",
    "eu5ab_regional_development__governor_refresh_now_desc": "Run a complete recalculation immediately and refresh the detail window.",
    "eu5ab_regional_development__governor_scoring_profile_name": "Location Value Profile",
    "eu5ab_regional_development__governor_scoring_profile_desc": "Weight potential tax base, population, and development. Scores are estimated from location values multiplied by expected Proximity improvements, rather than a final Control value; current Control is neither added nor deducted.",
    "eu5ab_regional_development__governor_scoring_profile_option_1_name": "Mixed",
    "eu5ab_regional_development__governor_scoring_profile_option_1_desc": "Balance economic and administrative-population value.",
    "eu5ab_regional_development__governor_scoring_profile_option_2_name": "Economic",
    "eu5ab_regional_development__governor_scoring_profile_option_2_desc": "Emphasize potential tax base and established economic scale.",
    "eu5ab_regional_development__governor_scoring_profile_option_3_name": "Administrative Population",
    "eu5ab_regional_development__governor_scoring_profile_option_3_desc": "Emphasize population and development.",
    "eu5ab_regional_development__governor_strategic_value_name": "Include Strategic Value",
    "eu5ab_regional_development__governor_strategic_value_desc": "Apply limited weight to ports, border locations, and fortified locations. This changes location value only and is not a separate score component.",
    "eu5ab_governor_window_title": "Governor Recommendation Details",
    "eu5ab_governor_window_intro": "View new-site and relocation suggestions. Building changes are up to you.",
    "eu5ab_governor_road_tier_help": "Estimates use the highest unlocked road tier; actual gains may differ.",
    "eu5ab_governor_refresh_button": "Recalculate",
    "eu5ab_governor_refresh_button_tt": "Reassess new sites, relocations, and layouts for Local and Naval Governor seats. Large countries may pause briefly; incomplete checks show a notice.",
    "eu5ab_governor_local_section": "Local Governor",
    "eu5ab_governor_local_diagnostics": (
        f"Last Local seat calculation: stage {_sync_value('stage')}, status {_sync_value('status')}; "
        f"capacity {_sync_value('capacity')}, engine count {_sync_value('occupied')} Local seats and "
        f"{_sync_value('lieutenancies')} Lieutenancies; other occupied slots {_sync_value('other_slots')}.\\n"
        f"Counted by location: {_sync_value('fresh_occupied')} Local seats and "
        f"{_sync_value('fresh_lieutenancies')} Lieutenancies; other occupied slots {_sync_value('fresh_other_slots')}; free slot (engine/location) "
        f"{_sync_value('slot_available')}/{_sync_value('fresh_slot_available')}; "
        f"mismatch {_sync_value('slot_cache_mismatch')} (1 means different).\\n"
        f"New site gain threshold {_sync_value('threshold', 1)}; "
        f"candidate sites {_sync_value('candidates')}, scored sites {_sync_value('shortlisted')}."
    ),
    "eu5ab_governor_naval_section": "Naval Governor",
    "eu5ab_governor_naval_diagnostics": "Last Naval seat calculation: status [GetPlayer.MakeScope.GetVariable('eu5ab_naval_gov_sync_status').GetValue|0]; refreshes [GetPlayer.MakeScope.GetVariable('eu5ab_naval_gov_sync_runs').GetValue|0].",
    "eu5ab_governor_new_slot_state": "A slot is available. You can build a seat at one of these sites.",
    "eu5ab_governor_empty_title": "No Suitable Candidate",
    "eu5ab_governor_no_recommendation": "#weak Recalculate after your territory or cities develop.#!",
    "eu5ab_governor_candidate_1": "Rank 1",
    "eu5ab_governor_candidate_2": "Rank 2",
    "eu5ab_governor_candidate_3": "Rank 3",
    "eu5ab_governor_view_location": "View Location",
    "eu5ab_governor_view_location_tt": "Move the map camera to this candidate.",
    "eu5ab_governor_local_candidate_1_name": "[GetPlayer.MakeScope.GetVariable('eu5ab_local_top_1').GetLocation.GetName]",
    "eu5ab_governor_local_candidate_2_name": "[GetPlayer.MakeScope.GetVariable('eu5ab_local_top_2').GetLocation.GetName]",
    "eu5ab_governor_local_candidate_3_name": "[GetPlayer.MakeScope.GetVariable('eu5ab_local_top_3').GetLocation.GetName]",
    "eu5ab_governor_naval_candidate_1_name": "[GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_1').GetLocation.GetName]",
    "eu5ab_governor_naval_candidate_2_name": "[GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_2').GetLocation.GetName]",
    "eu5ab_governor_naval_candidate_3_name": "[GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_3').GetLocation.GetName]",
    "eu5ab_governor_local_candidate_1_breakdown": "Overall score [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_1_score').GetValue|1] = Site Proximity Improvement Gain [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_1_site_gain').GetValue|1] + Surrounding Proximity Improvement Gain [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_1_surrounding_gain').GetValue|1].\\nProximity is expected to improve in [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_1_coverage').GetValue|0] locations (including the site).\\nScores are estimated by multiplying location values by expected Proximity increases, not a final Control value; current Control is neither added nor deducted, and actual Control continues to evolve through Max Control and normal game mechanics.",
    "eu5ab_governor_local_candidate_2_breakdown": "Overall score [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_2_score').GetValue|1] = Site Proximity Improvement Gain [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_2_site_gain').GetValue|1] + Surrounding Proximity Improvement Gain [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_2_surrounding_gain').GetValue|1].\\nProximity is expected to improve in [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_2_coverage').GetValue|0] locations (including the site).\\nScores are estimated by multiplying location values by expected Proximity increases, not a final Control value; current Control is neither added nor deducted, and actual Control continues to evolve through Max Control and normal game mechanics.",
    "eu5ab_governor_local_candidate_3_breakdown": "Overall score [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_3_score').GetValue|1] = Site Proximity Improvement Gain [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_3_site_gain').GetValue|1] + Surrounding Proximity Improvement Gain [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_3_surrounding_gain').GetValue|1].\\nProximity is expected to improve in [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_3_coverage').GetValue|0] locations (including the site).\\nScores are estimated by multiplying location values by expected Proximity increases, not a final Control value; current Control is neither added nor deducted, and actual Control continues to evolve through Max Control and normal game mechanics.",
    "eu5ab_governor_naval_candidate_1_breakdown": "Overall score [GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_1_score').GetValue|1] = Site Proximity Improvement Gain [GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_1_site_gain').GetValue|1] + Surrounding Proximity Improvement Gain [GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_1_surrounding_gain').GetValue|1].",
    "eu5ab_governor_naval_candidate_2_breakdown": "Overall score [GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_2_score').GetValue|1] = Site Proximity Improvement Gain [GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_2_site_gain').GetValue|1] + Surrounding Proximity Improvement Gain [GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_2_surrounding_gain').GetValue|1].",
    "eu5ab_governor_naval_candidate_3_breakdown": "Overall score [GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_3_score').GetValue|1] = Site Proximity Improvement Gain [GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_3_site_gain').GetValue|1] + Surrounding Proximity Improvement Gain [GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_3_surrounding_gain').GetValue|1].",
    "eu5ab_governor_migration_threshold": "An available slot is recommended immediately. Relocation requires at least 20% improvement, the minimum gain threshold, two consecutive evaluations, and a 12-month cooldown.",
    "eu5ab_governor_bounded_warning": "#warning Some assessments are incomplete; related suggestions are not shown.#!",
    "eu5ab_local_governor_available_alert_name": "A New Local Governor Seat Can Be Built",
    "eu5ab_local_governor_available_alert_tooltip": "Recommended: [GetPlayer.MakeScope.GetVariable('eu5ab_local_top_1').GetLocation.GetName]\\nThis site has the best regional marginal Proximity gain under the highest-road plan, excluding road improvements shared by existing seats. Left-click for details; right-click to hide; Shift+right-click to mute.",
    "eu5ab_local_governor_available_alert_icon": "@local_governor!",
    "eu5ab_local_governor_available_alert_color": "green",
    "eu5ab_local_governor_relocation_alert_name": "Relocate Local Governor",
    "eu5ab_local_governor_relocation_alert_icon": "@local_governor!",
    "eu5ab_local_governor_relocation_alert_color": "yellow",
    "eu5ab_naval_governor_available_alert_name": "A New Naval Governor Seat Can Be Built",
    "eu5ab_naval_governor_available_alert_tooltip": "Recommended: [GetPlayer.MakeScope.GetVariable('eu5ab_naval_top_1').GetLocation.GetName]\\nThis port is the best inland-coverage hub for a valuable disconnected part of the realm. Left-click for details; right-click to hide; Shift+right-click to mute.",
    "eu5ab_naval_governor_available_alert_icon": "@naval_governor!",
    "eu5ab_naval_governor_available_alert_color": "blue",
    "eu5ab_naval_governor_relocation_alert_name": "Relocate Naval Governor",
    "eu5ab_naval_governor_relocation_alert_icon": "@naval_governor!",
    "eu5ab_naval_governor_relocation_alert_color": "blue",
}

GOVERNOR_SIMP_CHINESE_LOCALIZATION.update(LAYOUT_SIMP_CHINESE)
GOVERNOR_ENGLISH_LOCALIZATION.update(LAYOUT_ENGLISH)
GOVERNOR_SIMP_CHINESE_LOCALIZATION.update({
    "eu5ab_regional_development__governor_relocation_enabled_name": "启用治所迁移建议",
    "eu5ab_regional_development__governor_relocation_enabled_desc": "提供现有治所的迁移建议。关闭后，手动刷新也只检查新建选址。",
    "eu5ab_regional_development__governor_migration_enabled_name": "自动重算治所迁移",
    "eu5ab_regional_development__governor_migration_enabled_desc": "在后台定期更新治所迁移建议。关闭后仍可手动刷新并查看结果。",
    "eu5ab_regional_development__governor_migration_threshold_percent_name": "地方治所迁移收益门槛（%）",
    "eu5ab_regional_development__governor_migration_threshold_percent_desc": "迁移带来的收益提升达到此比例时给出建议。Ctrl 每次调整 5%，Shift 每次调整 10%。",
})
GOVERNOR_ENGLISH_LOCALIZATION.update({
    "eu5ab_regional_development__governor_relocation_enabled_name": "Enable Seat Relocation Suggestions",
    "eu5ab_regional_development__governor_relocation_enabled_desc": "Suggest moves for existing seats. When disabled, manual refresh checks only new sites.",
    "eu5ab_regional_development__governor_migration_enabled_name": "Automatically Refresh Relocations",
    "eu5ab_regional_development__governor_migration_enabled_desc": "Update relocation suggestions periodically in the background. When disabled, you can still refresh manually and view the results.",
    "eu5ab_regional_development__governor_migration_threshold_percent_name": "Local Seat Relocation Gain (%)",
    "eu5ab_regional_development__governor_migration_threshold_percent_desc": "Suggest relocation when its gain reaches this percentage. Ctrl adjusts by 5%; Shift by 10%.",
})

for _rank in range(1, 4):
    _new_key = f"eu5ab_governor_naval_candidate_{_rank}_breakdown"
    # Keep the fixed-height card concise; lengthy explanations live in the docs.
    GOVERNOR_SIMP_CHINESE_LOCALIZATION[_new_key] = GOVERNOR_SIMP_CHINESE_LOCALIZATION[_new_key].split('\\n')[0]
    GOVERNOR_ENGLISH_LOCALIZATION[_new_key] = GOVERNOR_ENGLISH_LOCALIZATION[_new_key].split('\\n')[0]
    GOVERNOR_SIMP_CHINESE_LOCALIZATION[_new_key] += (
        "\\n仅估算陆地及海峡覆盖，未模拟海路。系统不会自动拆建。"
    )
    GOVERNOR_ENGLISH_LOCALIZATION[_new_key] += (
        "\\nLand/strait estimate only; sea routes not modeled. No automatic building changes."
    )


# One UI catalog, bound to two independent result namespaces.
for _catalog in (GOVERNOR_SIMP_CHINESE_LOCALIZATION, GOVERNOR_ENGLISH_LOCALIZATION):
    for _key, _value in list(_catalog.items()):
        if _key.startswith("eu5ab_layout_"):
            _catalog[NAVAL_PLANNER.bind_ui(_key)] = NAVAL_PLANNER.bind_ui(_value).replace("地方", "海军").replace("Local", "Naval")
    for _rank in range(1, 4):
        _key = f"eu5ab_governor_local_candidate_{_rank}_breakdown"
        _catalog[_key.replace("_local_", "_naval_")] = NAVAL_PLANNER.bind_ui(_catalog[_key])
    for _status in (1, 2, 3, 4, 6):
        _catalog[f"eu5ab_governor_naval_status_{_status}"] = _catalog[f"eu5ab_governor_local_status_{_status}"]
    _catalog["eu5ab_governor_refresh_empty"] = ""

GOVERNOR_SIMP_CHINESE_LOCALIZATION.update({
    "eu5ab_regional_development__naval_governor_migration_threshold_percent_name": "海军治所迁移收益门槛（%）",
    "eu5ab_regional_development__naval_governor_migration_threshold_percent_desc": "独立设置海军治所迁移收益门槛，默认80%，范围0–200%。普通/Ctrl/Shift点击调整1/5/10个百分点。关闭自动重算仍可调整及手动重算。",
    "eu5ab_governor_refresh_button_tt": "重新评估地方和海军治所的新建、迁移及布局建议。大国可能短暂卡顿，未完成时会显示提示。",
    "eu5ab_regional_development__governor_refresh_now_desc": "立即重新计算地方与海军治所建议，暂停时也有效。大型国家可能短暂卡顿。",
    "eu5ab_governor_migration_threshold": "迁移收益门槛：地方 [GetPlayer.MakeScope.GetVariable('eu5ab_global_governor_migration_threshold_percent').GetValue|0]%；海军 [GetPlayer.MakeScope.GetVariable('eu5ab_global_naval_governor_migration_threshold_percent').GetValue|0]%。",
    "eu5ab_governor_refresh_progress": "[SelectLocalization(GetPlayer.MakeScope.GetVariable('eu5ab_governor_scan_active').IsSet, 'eu5ab_governor_local_running', 'eu5ab_governor_refresh_empty')] [SelectLocalization(GetPlayer.MakeScope.GetVariable('eu5ab_naval_planner_scan_active').IsSet, 'eu5ab_governor_naval_running', 'eu5ab_governor_refresh_empty')]",
    "eu5ab_governor_local_running": "地方治所正在计算。",
    "eu5ab_governor_naval_running": "海军治所正在计算。",
    "eu5ab_governor_refresh_failure": "[SelectLocalization(GetPlayer.MakeScope.GetVariable('eu5ab_layout_failed').IsSet, 'eu5ab_governor_local_failed', 'eu5ab_governor_refresh_empty')] [SelectLocalization(GetPlayer.MakeScope.GetVariable('eu5ab_naval_layout_failed').IsSet, 'eu5ab_governor_naval_failed', 'eu5ab_governor_refresh_empty')]",
    "eu5ab_governor_local_failed": "地方刷新未完成，请重试；保留的结果属于上次计算。",
    "eu5ab_governor_naval_failed": "海军刷新未完成，请重试；保留的结果属于上次计算。",
})
GOVERNOR_ENGLISH_LOCALIZATION.update({
    "eu5ab_regional_development__naval_governor_migration_threshold_percent_name": "Naval Seat Relocation Gain (%)",
    "eu5ab_regional_development__naval_governor_migration_threshold_percent_desc": "Independent naval relocation threshold: default 80%, range 0–200%. Normal/Ctrl/Shift clicks adjust 1/5/10 percentage points. Available with automatic refresh off.",
    "eu5ab_governor_refresh_button_tt": "Reassess new sites, relocations, and layouts for Local and Naval Governor seats. Large countries may pause briefly; incomplete checks show a notice.",
    "eu5ab_regional_development__governor_refresh_now_desc": "Recalculate Local and Naval seat recommendations now, including while paused. Large countries may briefly pause.",
    "eu5ab_governor_migration_threshold": "Relocation gain threshold: Local [GetPlayer.MakeScope.GetVariable('eu5ab_global_governor_migration_threshold_percent').GetValue|0]%; Naval [GetPlayer.MakeScope.GetVariable('eu5ab_global_naval_governor_migration_threshold_percent').GetValue|0]%.",
    "eu5ab_governor_refresh_progress": GOVERNOR_SIMP_CHINESE_LOCALIZATION["eu5ab_governor_refresh_progress"],
    "eu5ab_governor_local_running": "Calculating Local seats.",
    "eu5ab_governor_naval_running": "Calculating Naval seats.",
    "eu5ab_governor_refresh_failure": GOVERNOR_SIMP_CHINESE_LOCALIZATION["eu5ab_governor_refresh_failure"],
    "eu5ab_governor_local_failed": "Local refresh incomplete; retry. Retained results are from the previous calculation.",
    "eu5ab_governor_naval_failed": "Naval refresh incomplete; retry. Retained results are from the previous calculation.",
})
GOVERNOR_SIMP_CHINESE_LOCALIZATION["eu5ab_governor_road_tier_help"] += "\\n两类方案分别固定另一类现状；执行任一方案后应重算，收益不能相加。"
GOVERNOR_ENGLISH_LOCALIZATION["eu5ab_governor_road_tier_help"] += "\\nEach plan holds the other seat type fixed. Recalculate after changes; gains cannot be added."


def render_governor_script_values(*, registered_dlcs: frozenset[str] = frozenset()) -> str:
    values = """# Generated by eu5autobuild.governor_generator.
# Proximity uses the vanilla 0-100 scale. Control and Maximum Control use 0-1.
# Control is a downstream value: Proximity is the main input to Max Control,
# while integration, satisfaction, armies, and buildings can also modify it.
# The recommendation score therefore does not invent a Control multiplier.

eu5ab_governor_potential_tax_base = {
\t# Current tax base scales with current control, not its future maximum.
\t# At zero control, wealth cannot be recovered from the current tax base.
\tvalue = 0
\tif = {
\t\tlimit = { local_control > 0 }
\t\tvalue = location_tax_base
\t\tdivide = local_control
\t}
}

# A compact value model avoids counting correlated size metrics at full weight.
# 1 = mixed, 2 = economic, 3 = administrative population.
eu5ab_governor_location_value = {
\tif = {
\t\tlimit = { owner.var:eu5ab_global_governor_scoring_profile = 2 }
\t\tvalue = { value = eu5ab_governor_potential_tax_base multiply = 2.5 }
\t\tadd = { value = population multiply = 0.15 }
\t\tadd = { value = development multiply = 0.75 }
\t}
\telse_if = {
\t\tlimit = { owner.var:eu5ab_global_governor_scoring_profile = 3 }
\t\tvalue = { value = eu5ab_governor_potential_tax_base multiply = 0.25 }
\t\tadd = { value = population multiply = 1.2 }
\t\tadd = { value = development multiply = 0.75 }
\t}
\telse = {
\t\tvalue = { value = eu5ab_governor_potential_tax_base multiply = 1.5 }
\t\tadd = { value = population multiply = 0.5 }
\t\tadd = { value = development multiply = 0.75 }
\t}
\tif = {
\t\tlimit = { owner.var:eu5ab_global_governor_strategic_value > 0 }
\t\tif = { limit = { is_port = yes } multiply = 1.15 }
\t\tif = { limit = { has_fort = yes } multiply = 1.1 }
\t\tif = {
\t\t\tlimit = {
\t\t\t\tany_neighbor_location = {
\t\t\t\t\thas_owner = yes
\t\t\t\t\tNOT = { owner ?= prev.owner }
\t\t\t\t}
\t\t\t}
\t\t\tmultiply = 1.1
\t\t}
\t}
\tmin = 0.01
}

eu5ab_governor_node_marginal_gain = {
\tvalue = var:eu5ab_gov_predicted
\tsubtract = eu5ab_governor_comparison_proximity
\tmin = 0
\tdivide = 100
\tmultiply = var:eu5ab_gov_node_value
}

{transport_values}

# Preserve the raw additive source, including the capital and temporary effects.
# Subtract only the moving seat's 80 points BEFORE clamping propagation to 0-100.
eu5ab_governor_current_proximity_source = {
\tvalue = modifier:local_proximity_source
}

# Vanilla 1.4: registered AND enabled DLC makes Lieutenancies independent.
# Unregistered DLC must not be referenced: has_dlc fails during post-validation.
eu5ab_governor_local_other_slots = {
\tvalue = total_building_levels_including_construction:itinerant_court_seat
\tadd = total_building_levels_including_construction:kings_manor
\tif = { limit = { {lieutenancy_uses_local_slot} }
\t\tadd = total_building_levels_including_construction:lieutenancy
\t}
}
eu5ab_governor_fresh_local_other_slots = {
\tvalue = var:eu5ab_gov_fresh_itinerant_seats
\tadd = var:eu5ab_gov_fresh_kings_manors
\tif = { limit = { {lieutenancy_uses_local_slot} }
\t\tadd = var:eu5ab_gov_fresh_lieutenancies
\t}
}

eu5ab_governor_refresh_months = {
\tif = { limit = { var:eu5ab_global_governor_refresh_interval = 1 } value = 1 }
\telse_if = { limit = { var:eu5ab_global_governor_refresh_interval = 3 } value = 6 }
\telse_if = { limit = { var:eu5ab_global_governor_refresh_interval = 4 } value = 12 }
\telse = { value = 3 }
}

# Cap unused-slot alerts so national growth cannot suppress useful local sites.
eu5ab_governor_new_recommendation_threshold = {
\tvalue = var:eu5ab_governor_total_value
\tmultiply = 0.01
\tmin = 1
\tmax = 1000
}

# Keep the existing full-layout selection policy independent of alert tuning.
eu5ab_governor_layout_candidate_threshold = {
\tvalue = var:eu5ab_governor_total_value
\tmultiply = 0.01
\tmin = 1
}

eu5ab_governor_migration_absolute_threshold = {
\tvalue = var:eu5ab_governor_total_value
\tmultiply = 0.02
\tmin = 2
}
""".replace("{transport_values}", render_transport_values()).replace(
        "{lieutenancy_uses_local_slot}",
        'NOT = { has_dlc = "d009_across_the_pillars" }'
        if "d009_across_the_pillars" in registered_dlcs else "always = yes",
    )
    values += '''
eu5ab_governor_relocation_capacity = {
    value = var:eu5ab_gov_fresh_local_capacity
    subtract = eu5ab_governor_fresh_local_other_slots
}
eu5ab_governor_relocation_occupied = {
    value = var:eu5ab_gov_fresh_local_occupied
}
'''
    cached_value = script_definition(values, "eu5ab_governor_location_value")
    cached_value = cached_value.replace("eu5ab_governor_location_value", "eu5ab_governor_cached_location_value")
    for source, target in (("eu5ab_governor_potential_tax_base", "var:eu5ab_gov_cached_potential_tax_base"),
                           ("value = population", "value = var:eu5ab_gov_cached_population"),
                           ("value = development", "value = var:eu5ab_gov_cached_development")):
        cached_value = cached_value.replace(source, target)
    values += "\n" + cached_value
    naval_values = NAVAL_PLANNER.bind(values)
    for local_only in ("local_other_slots", "fresh_local_other_slots"):
        naval_values = naval_values.replace(script_definition(naval_values, "eu5ab_naval_planner_" + local_only), "")
    naval_values = naval_values.replace(
        script_definition(naval_values, "eu5ab_naval_planner_relocation_capacity"),
        "eu5ab_naval_planner_relocation_capacity = {\n    value = var:eu5ab_naval_gov_fresh_naval_capacity\n}")
    naval_values = naval_values.replace(
        script_definition(naval_values, "eu5ab_naval_planner_relocation_occupied"),
        "eu5ab_naval_planner_relocation_occupied = {\n    value = var:eu5ab_naval_gov_fresh_naval_occupied\n}")
    return values + "\n" + naval_values


def render_governor_triggers() -> str:
    triggers = f"""# Generated by eu5autobuild.governor_generator.
eu5ab_local_governor_slot_available = {{
\ttotal_building_levels_including_construction:local_governor < {{
\t\tvalue = effective_num_local_governors
\t\tsubtract = eu5ab_governor_local_other_slots
\t}}
}}

eu5ab_naval_governor_slot_available = {{
\tmodifier:num_naval_governors > 0
\ttotal_building_levels_including_construction:naval_governor < modifier:num_naval_governors
}}

# Rebuilt from structural records at the start of each recommendation pass.
eu5ab_fresh_local_governor_slot_available = {{
\tvar:eu5ab_gov_fresh_local_occupied < {{
\t\tvalue = var:eu5ab_gov_fresh_local_capacity
\t\tsubtract = eu5ab_governor_fresh_local_other_slots
\t}}
}}

# Structural filter used for relocation as well as new slots. It mirrors the
# vanilla location potential and non-slot allow conditions without invoking the
# construction-UI can-build trigger, whose vanilla allow block requires actor.
eu5ab_local_governor_candidate = {{
\thas_owner = yes
\towner ?= root
\towner.capital != this
\tOR = {{
\t\tlocation_rank = location_rank:city
\t\tlocation_rank = location_rank:megalopolis
\t}}
\thas_road_to_capital = yes
\tNOT = {{ has_building = building_type:local_governor }}
\tNOT = {{ has_building = building_type:itinerant_court_seat }}
\tNOT = {{ has_building = building_type:kings_manor }}
\tNOT = {{ has_building = building_type:seljuk_mint }}
\tNOT = {{ any_buildings_in_location = {{ building_type = building_type:local_governor building_levels_under_construction > 0 }} }}
\tNOT = {{ any_buildings_in_location = {{ OR = {{ building_type = building_type:itinerant_court_seat building_type = building_type:kings_manor }} building_levels_under_construction > 0 }} }}
}}

eu5ab_naval_governor_candidate = {{
\thas_owner = yes
\towner ?= root
\tOR = {{
\t\tlocation_rank = location_rank:city
\t\tlocation_rank = location_rank:megalopolis
\t}}
\tis_port = yes
\tNOT = {{ is_connected_to_through_realm = owner.capital }}
\tis_overseas_for_owner = no
\tNOT = {{ has_building = building_type:naval_governor }}
\tNOT = {{ any_buildings_in_location = {{ building_type = building_type:naval_governor building_levels_under_construction > 0 }} }}
}}

"""
    return render_connection_trigger() + render_refresh_triggers() + NAVAL_PLANNER.bind(render_refresh_triggers()) + triggers + "\n" + """eu5ab_fresh_naval_governor_slot_available = {
    var:eu5ab_naval_gov_fresh_naval_occupied < var:eu5ab_naval_gov_fresh_naval_capacity
}
"""


def render_governor_events() -> str:
    return """# Generated by eu5autobuild.governor_generator.
namespace = eu5ab_governor

eu5ab_governor.1 = {
\ttype = country_event
\ttitle = eu5ab_governor_window_title
\toutcome = neutral
\thidden = yes
\timmediate = {
\t\t# The event owns this marker, even when recommendations were disabled
\t\t# while it was waiting in the event queue.
\t\tremove_variable = eu5ab_governor_recalculation_scheduled
\t\tif = {
\t\t\tlimit = { has_variable = eu5ab_governor_skip_next_scheduled_event }
\t\t\tremove_variable = eu5ab_governor_skip_next_scheduled_event
\t\t}
\t\telse = { eu5ab_governor_run_scheduled_planners = yes }
\t}
}

eu5ab_governor.2 = {
\ttype = country_event
\ttitle = eu5ab_governor_window_title
\toutcome = neutral
\thidden = yes
\timmediate = { eu5ab_layout_watchdog = yes }
}

eu5ab_governor.3 = {
\ttype = country_event
\ttitle = eu5ab_governor_window_title
\toutcome = neutral
\thidden = yes
\timmediate = { eu5ab_naval_layout_watchdog = yes }
}
"""


def render_governor_scripted_guis() -> str:
    chunks = ["# Generated by eu5autobuild.governor_generator."]
    chunks.append("""eu5ab_gui_governor_refresh_now = {
\tscope = country
\tis_shown = { is_human = yes }
\tis_valid = { is_human = yes }
\teffect = {
\t\teu5ab_governor_manual_recalculation = yes
\t}
}

eu5ab_gui_governor_close = {
\tscope = country
\tis_shown = { is_human = yes }
\tis_valid = { is_human = yes }
\teffect = { remove_variable = eu5ab_governor_window_requested }
}
""")
    for kind in ("local", "naval"):
        for rank in range(1, 4):
            chunks.append(f"""eu5ab_gui_pan_{kind}_governor_{rank} = {{
\tscope = country
\tis_shown = {{ has_variable = eu5ab_{kind}_top_{rank} var:eu5ab_{kind}_top_{rank} = {{ eu5ab_{kind}_governor_candidate = yes }} }}
\tis_valid = {{ has_variable = eu5ab_{kind}_top_{rank} var:eu5ab_{kind}_top_{rank} = {{ eu5ab_{kind}_governor_candidate = yes }} }}
\teffect = {{}}
}}
""")
    return "\n".join(chunks) + "\n" + render_layout_scripted_guis() + "\n" + render_layout_scripted_guis(NAVAL_PLANNER)


def _governor_candidate_card(kind: str, rank: int) -> str:
    y_offset = (rank - 1) * 162
    return f"""widget = {{
\t\tname = "eu5ab_{kind}_candidate_{rank}_card"
\t\tposition = {{ 0 {y_offset} }}
\t\tlayoutpolicy_horizontal = fixed
\t\tlayoutpolicy_vertical = fixed
\t\tminimumsize = {{ 524 154 }}
\t\tmaximumsize = {{ 524 154 }}
\t\tsize = {{ 524 154 }}
\t\tvisible = "[GetScriptedGui('eu5ab_gui_pan_{kind}_governor_{rank}').IsShown(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
\t\tdatamodel = "[GetPlayer.MakeScope.GetList('eu5ab_{kind}_top_{rank}_list')]"
\t\titem = {{
\t\t\twidget = {{
\t\t\t\tdatacontext = "[Scope.GetLocation]"
\t\t\t\tlayoutpolicy_horizontal = fixed
\t\t\t\tlayoutpolicy_vertical = fixed
\t\t\t\tminimumsize = {{ 524 154 }}
\t\t\t\tmaximumsize = {{ 524 154 }}
\t\t\t\tsize = {{ 524 154 }}
\t\t\t\tvbox = {{
\t\t\t\t\tlayoutpolicy_horizontal = fixed
\t\t\t\t\tlayoutpolicy_vertical = fixed
\t\t\t\t\tminimumsize = {{ 524 154 }}
\t\t\t\t\tmaximumsize = {{ 524 154 }}
\t\t\t\t\tsize = {{ 524 154 }}
\t\t\t\t\tusing = bg_square_wood_tile
\t\t\t\t\tusing = bg_cabinet_card_frame
\t\t\t\t\tmargin = {{ 14 12 }}
\t\t\t\t\tspacing = 6
\t\t\t\t\thbox = {{
\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\tlayoutpolicy_vertical = fixed
\t\t\t\t\t\tsize = {{ -1 32 }}
\t\t\t\t\t\tspacing = 8
\t\t\t\t\t\ttext_single = {{
\t\t\t\t\t\t\tsize = {{ 66 30 }}
\t\t\t\t\t\t\tautoresize = no
\t\t\t\t\t\t\talign = center|nobaseline
\t\t\t\t\t\t\tfontsize = 14
\t\t\t\t\t\t\tfontsize_min = 11
\t\t\t\t\t\t\tusing = bg_number_container_bckg
\t\t\t\t\t\t\ttext = "eu5ab_governor_candidate_{rank}"
\t\t\t\t\t\t}}
\t\t\t\t\t\ttext_single = {{
\t\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\t\tsize = {{ -1 30 }}
\t\t\t\t\t\t\tautoresize = no
\t\t\t\t\t\t\talign = left|vcenter
\t\t\t\t\t\t\tfontsize = 17
\t\t\t\t\t\t\tfontsize_min = 12
\t\t\t\t\t\t\tdefault_format = "#yellow_titles"
\t\t\t\t\t\t\telide = right
\t\t\t\t\t\t\ttext = "[Location.GetName]"
\t\t\t\t\t\t}}
\t\t\t\t\t\tbutton_regular = {{
\t\t\t\t\t\t\tsize = {{ 112 30 }}
\t\t\t\t\t\t\ttext = "eu5ab_governor_view_location"
\t\t\t\t\t\t\ttooltip = "eu5ab_governor_view_location_tt"
\t\t\t\t\t\t\tonclick = "[PanToLocation(Location.Self)]"
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t\ttext_multi = {{
\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\tlayoutpolicy_vertical = fixed
\t\t\t\t\t\tsize = {{ -1 92 }}
\t\t\t\t\t\tautoresize = no
\t\t\t\t\t\talign = left|top
\t\t\t\t\t\tfontsize = 13
\t\t\t\t\t\tfontsize_min = 11
\t\t\t\t\t\ttext = "eu5ab_governor_{kind}_candidate_{rank}_breakdown"
\t\t\t\t\t}}
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t}}"""


def _governor_recommendation_panel(kind: str, cards: str) -> str:
    status = ""
    if kind == "local":
        for code in (1, 2, 3, 4, 6):
            status += f'''text_multi = {{
                position = {{ 0 0 }} size = {{ 524 44 }}
                autoresize = no fontsize = 13 fontsize_min = 11
                visible = "[EqualTo_CFixedPoint(GetPlayer.MakeScope.GetVariable('eu5ab_gov_sync_status').GetValue, '(CFixedPoint){code}')]"
                text = "eu5ab_governor_local_status_{code}"
            }}
'''
    return f"""widget = {{
\t\t\t\tname = "eu5ab_governor_{kind}_panel"
\t\t\t\tlayoutpolicy_horizontal = fixed
\t\t\t\tlayoutpolicy_vertical = expanding
\t\t\t\tminimumsize = {{ 544 600 }}
\t\t\t\tmaximumsize = {{ 544 2000 }}
\t\t\t\tsize = {{ 544 600 }}
\t\t\t\tusing = bg_secondary_inner_alt
\t\t\t\twidget = {{
\t\t\t\t\tposition = {{ 10 10 }}
\t\t\t\t\tsize = {{ 524 580 }}
\t\t\t\t\ttext_single = {{
\t\t\t\t\t\tposition = {{ 0 0 }}
\t\t\t\t\t\tsize = {{ 524 42 }}
\t\t\t\t\t\tautoresize = no
\t\t\t\t\t\talign = left|vcenter
\t\t\t\t\t\tdefault_format = "#yellow_titles"
\t\t\t\t\t\tfontsize = 20
\t\t\t\t\t\tfontsize_min = 16
\t\t\t\t\t\ttext = "eu5ab_governor_{kind}_section"
\t\t\t\t\t}}
\t\t\t\t\twidget = {{
\t\t\t\t\t\tposition = {{ 0 50 }}
\t\t\t\t\t\tsize = {{ 524 44 }}
{status}
\t\t\t\t\t\ttext_multi = {{
\t\t\t\t\t\t\tposition = {{ 0 0 }}
\t\t\t\t\t\t\tsize = {{ 524 44 }}
\t\t\t\t\t\t\tautoresize = no
\t\t\t\t\t\t\talign = left|vcenter
\t\t\t\t\t\t\tfontsize = 14
\t\t\t\t\t\t\tfontsize_min = 11
\t\t\t\t\t\t\tvisible = "[GetPlayer.MakeScope.GetVariable('eu5ab_{kind}_has_new_recommendation').IsSet]"
\t\t\t\t\t\t\ttext = "eu5ab_governor_new_slot_state"
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t\twidget = {{
\t\t\t\t\t\tposition = {{ 0 102 }}
\t\t\t\t\t\tsize = {{ 524 478 }}
{cards}
\t\t\t\t\t\twidget = {{
\t\t\t\t\t\t\tname = "eu5ab_governor_{kind}_empty_state"
\t\t\t\t\t\t\tposition = {{ 0 0 }}
\t\t\t\t\t\t\tsize = {{ 524 220 }}
\t\t\t\t\t\t\tvisible = "[Not(GetPlayer.MakeScope.GetVariable('eu5ab_{kind}_top_1').IsSet)]"
\t\t\t\t\t\t\ttext_single = {{
\t\t\t\t\t\t\t\tposition = {{ 32 52 }}
\t\t\t\t\t\t\t\tsize = {{ 460 32 }}
\t\t\t\t\t\t\t\tautoresize = no
\t\t\t\t\t\t\t\talign = center|nobaseline
\t\t\t\t\t\t\t\tdefault_format = "#yellow_titles"
\t\t\t\t\t\t\t\tfontsize = 17
\t\t\t\t\t\t\t\tfontsize_min = 13
\t\t\t\t\t\t\t\ttext = "eu5ab_governor_empty_title"
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\ttext_multi = {{
\t\t\t\t\t\t\t\tposition = {{ 32 94 }}
\t\t\t\t\t\t\t\tsize = {{ 460 104 }}
\t\t\t\t\t\t\t\tautoresize = no
\t\t\t\t\t\t\t\talign = hcenter|top
\t\t\t\t\t\t\t\tfontsize = 14
\t\t\t\t\t\t\t\tfontsize_min = 11
\t\t\t\t\t\t\t\ttext = "eu5ab_governor_no_recommendation"
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t}}
\t\t\t}}"""


def render_governor_gui() -> str:
    local_cards = "\n".join(_governor_candidate_card("local", rank) for rank in range(1, 4))
    legacy_local_panel = _governor_recommendation_panel("local", local_cards)
    local_panel = render_layout_panel(legacy_local_panel)
    naval_panel = render_layout_panel(legacy_local_panel, NAVAL_PLANNER)
    return f"""# Generated by eu5autobuild.governor_generator.
window = {{
\tname = "eu5ab_governor_recommendation_window"
\tdatacontext = "[GetPlayer]"
\tallow_outside = yes
\talwaystransparent = no
\tparentanchor = center
\tposition = {{ 0 0 }}
\tmovable = yes
\tsize = {{ 1120 864 }}
\tvisible = "[Or(GetVariableSystem.Exists('eu5ab_governor_window'), GetPlayer.MakeScope.GetVariable('eu5ab_governor_window_requested').IsSet)]"
\tenabled = "[Or(GetVariableSystem.Exists('eu5ab_governor_window'), GetPlayer.MakeScope.GetVariable('eu5ab_governor_window_requested').IsSet)]"

\twidget = {{
\t\tsize = {{ 1120 864 }}
\t\tusing = bg_window_default_alt

\t\tvbox = {{
\t\t\tlayoutpolicy_horizontal = fixed
\t\t\tlayoutpolicy_vertical = fixed
\t\t\tsize = {{ 1120 864 }}
\t\t\tusing = window_margin_alt
\t\t\tspacing = 10
\t\t\thbox = {{
\t\t\t\tname = "eu5ab_governor_title_bar"
\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\tlayoutpolicy_vertical = fixed
\t\t\t\tsize = {{ -1 50 }}
\t\t\t\tusing = bg_square_wood_tile
\t\t\t\tusing = bg_cabinet_card_frame
\t\t\t\tmargin = {{ 8 4 }}
\t\t\t\twidget = {{ size = {{ 40 40 }} }}
\t\t\t\ttext_single = {{
\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\tsize = {{ -1 42 }}
\t\t\t\t\tautoresize = no
\t\t\t\t\talign = center|nobaseline
\t\t\t\t\tdefault_format = "#yellow_titles"
\t\t\t\t\tfontsize = 22
\t\t\t\t\tfontsize_min = 17
\t\t\t\t\ttext = "eu5ab_governor_window_title"
\t\t\t\t}}
\t\t\t\twidget = {{
\t\t\t\t\tsize = {{ 40 40 }}
\t\t\t\t\tbutton_close_alt = {{
\t\t\t\t\t\tblockoverride "close_on_action" {{
\t\t\t\t\t\t\ton_action = "[GetVariableSystem.Clear('eu5ab_governor_window')]"
\t\t\t\t\t\t\ton_action = "[GetScriptedGui('eu5ab_gui_governor_close').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t}}
\t\t\t}}
\t\t\tvbox = {{
\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\tlayoutpolicy_vertical = fixed
\t\t\t\tsize = {{ -1 160 }}
\t\t\t\tusing = bg_secondary_inner_alt
\t\t\t\tmargin = {{ 12 10 }}
\t\t\t\tspacing = 4
\t\t\t\tignoreinvisible = yes
\t\t\t\thbox = {{
\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\tlayoutpolicy_vertical = fixed
\t\t\t\t\tsize = {{ -1 80 }}
\t\t\t\t\tspacing = 12
\t\t\t\t\tvbox = {{
\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\tlayoutpolicy_vertical = fixed
\t\t\t\t\t\tsize = {{ -1 80 }}
\t\t\t\t\t\tspacing = 2
\t\t\t\t\t\ttext_multi = {{
\t\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\t\tsize = {{ -1 48 }}
\t\t\t\t\t\t\tautoresize = no
\t\t\t\t\t\t\tfontsize = 14
\t\t\t\t\t\t\tfontsize_min = 12
\t\t\t\t\t\t\ttext = "eu5ab_governor_window_intro"
\t\t\t\t\t\t\ttooltip = "eu5ab_governor_road_tier_help"
\t\t\t\t\t\t}}
\t\t\t\t\t\ttext_multi = {{
\t\t\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\t\t\tsize = {{ -1 28 }}
\t\t\t\t\t\t\tautoresize = no
\t\t\t\t\t\t\tfontsize = 13
\t\t\t\t\t\t\tfontsize_min = 11
\t\t\t\t\t\t\tvisible = "[GreaterThan_CFixedPoint(GetPlayer.MakeScope.GetVariable('eu5ab_global_governor_relocation_enabled').GetValue, '(CFixedPoint)0')]"
\t\t\t\t\t\t\ttext = "eu5ab_governor_migration_threshold"
\t\t\t\t\t\t}}
\t\t\t\t\t}}
\t\t\t\t\tbutton_regular = {{
\t\t\t\t\t\tsize = {{ 156 40 }}
\t\t\t\t\t\ttext = "eu5ab_governor_refresh_button"
\t\t\t\t\t\ttooltip = "eu5ab_governor_refresh_button_tt"
\t\t\t\t\t\tonclick = "[GetScriptedGui('eu5ab_gui_governor_refresh_now').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
\t\t\t\t\t}}
\t\t\t\t}}
\t\t\t\ttext_multi = {{
\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\tsize = {{ -1 24 }}
\t\t\t\t\tautoresize = no
\t\t\t\t\tfontsize = 12
\t\t\t\t\tvisible = "[Or(GetPlayer.MakeScope.GetVariable('eu5ab_governor_queue_exhausted').IsSet, GetPlayer.MakeScope.GetVariable('eu5ab_naval_planner_queue_exhausted').IsSet)]"
\t\t\t\t\ttext = "eu5ab_governor_bounded_warning"
\t\t\t\t}}
\t\t\t\ttext_multi = {{
\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\tsize = {{ -1 28 }} autoresize = no fontsize = 12 fontsize_min = 10
\t\t\t\t\tvisible = "[Or(GetPlayer.MakeScope.GetVariable('eu5ab_governor_scan_active').IsSet, GetPlayer.MakeScope.GetVariable('eu5ab_naval_planner_scan_active').IsSet)]"
\t\t\t\t\ttext = "eu5ab_governor_refresh_progress"
\t\t\t\t}}
\t\t\t\ttext_multi = {{
\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\tsize = {{ -1 28 }} autoresize = no fontsize = 12 fontsize_min = 10
\t\t\t\t\tvisible = "[Or(GetPlayer.MakeScope.GetVariable('eu5ab_layout_failed').IsSet, GetPlayer.MakeScope.GetVariable('eu5ab_naval_layout_failed').IsSet)]"
\t\t\t\t\ttext = "eu5ab_governor_refresh_failure"
\t\t\t\t}}
\t\t\t}}
\t\t\thbox = {{
\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\tlayoutpolicy_vertical = expanding
\t\t\t\tminimumsize = {{ 0 600 }}
\t\t\t\tspacing = 12
{local_panel}
{naval_panel}
\t\t\t}}
\t\t}}
\t}}
}}
"""


def _render_migration_cleanup_effects() -> str:
    template = """eu5ab_governor_clear_@KIND@_migration = {
\tcmf_remove_alert = { alert = eu5ab_@KIND@_governor_relocation_alert }
\tremove_variable = eu5ab_@KIND@_has_migration
}
"""
    return "\n".join(
        template.replace("@KIND@", kind) for kind in ("local", "naval")
    )


def render_governor_effects(straits: dict[str, list[str]] | None = None) -> str:
    effects = """# Generated by eu5autobuild.governor_generator.
# Recommendation only: this file never constructs, removes, or destroys a building.

eu5ab_register_governor_alerts = {
\tcmf_set_alert_open_window = { alert = eu5ab_local_governor_available_alert window = eu5ab_governor_window }
\tcmf_set_alert_open_window = { alert = eu5ab_local_governor_relocation_alert window = eu5ab_governor_window }
\tcmf_set_alert_open_window = { alert = eu5ab_naval_governor_available_alert window = eu5ab_governor_window }
\tcmf_set_alert_open_window = { alert = eu5ab_naval_governor_relocation_alert window = eu5ab_governor_window }
}

eu5ab_prepare_governor_window = {
\teu5ab_governor_ensure_planner_schema = yes
\teu5ab_governor_check_transport_rules = yes
\teu5ab_naval_planner_check_transport_rules = yes
\t# The CMF alert manager sets the matching VariableSystem key. This effect is
\t# intentionally script-only so alert clicks also refresh saved diagnostics.
\tif = {
\t\tlimit = { OR = { NOT = { has_variable = eu5ab_governor_last_run_year } has_variable = eu5ab_governor_dirty has_variable = eu5ab_naval_planner_dirty } }
\t\tset_variable = eu5ab_governor_dirty
\t\teu5ab_schedule_governor_recalculation = yes
\t}
}

eu5ab_governor_dirty_from_owner_change = {
\tscope:winner ?= { if = { limit = { is_human = yes } set_variable = eu5ab_governor_dirty set_variable = eu5ab_naval_planner_dirty } }
\tscope:loser ?= { if = { limit = { is_human = yes } set_variable = eu5ab_governor_dirty set_variable = eu5ab_naval_planner_dirty } }
}

eu5ab_governor_monthly_pulse = {
\tif = {
\t\tlimit = { is_human = yes }
\t\teu5ab_governor_ensure_planner_schema = yes
\t\teu5ab_governor_check_transport_rules = yes
\t\teu5ab_naval_planner_check_transport_rules = yes
\t\t# Enroll active scans restored from saves predating the watchdog.
\t\teu5ab_layout_schedule_watchdog = yes
\t\teu5ab_naval_layout_schedule_watchdog = yes
\t\tif = { limit = { NOT = { has_variable = eu5ab_governor_months_since_refresh } } set_variable = { name = eu5ab_governor_months_since_refresh value = 0 } }
\t\tchange_variable = { name = eu5ab_governor_months_since_refresh add = 1 }
\t\t# Zero-valued counters can disappear. Copy the old shared cadence once,
\t\t# then advance the naval counter independently on later monthly pulses.
\t\tif = { limit = { NOT = { has_variable = eu5ab_naval_planner_refresh_counter_initialized } } set_variable = { name = eu5ab_naval_planner_months_since_refresh value = var:eu5ab_governor_months_since_refresh } set_variable = eu5ab_naval_planner_refresh_counter_initialized }
\t\telse_if = { limit = { has_variable = eu5ab_naval_planner_months_since_refresh } change_variable = { name = eu5ab_naval_planner_months_since_refresh add = 1 } }
\t\telse = { set_variable = { name = eu5ab_naval_planner_months_since_refresh value = 1 } }
\t\tif = { limit = { has_variable = eu5ab_local_migration_cooldown var:eu5ab_local_migration_cooldown > 0 } change_variable = { name = eu5ab_local_migration_cooldown subtract = 1 } }
\t\tif = { limit = { has_variable = eu5ab_naval_migration_cooldown var:eu5ab_naval_migration_cooldown > 0 } change_variable = { name = eu5ab_naval_migration_cooldown subtract = 1 } }
\t\tif = { limit = { NOT = { has_variable = eu5ab_governor_scan_active } var:eu5ab_governor_months_since_refresh >= eu5ab_governor_refresh_months } set_variable = eu5ab_governor_dirty }
\t\tif = { limit = { NOT = { has_variable = eu5ab_naval_planner_scan_active } var:eu5ab_naval_planner_months_since_refresh >= eu5ab_governor_refresh_months } set_variable = eu5ab_naval_planner_dirty }
\t\tif = {
\t\t\tlimit = {
\t\t\t\tvar:eu5ab_global_governor_recommendations_enabled > 0
\t\t\t\tNOT = { has_variable = eu5ab_governor_scan_active }
\t\t\t\tOR = {
\t\t\t\t\thas_variable = eu5ab_governor_dirty
\t\t\t\t\thas_variable = eu5ab_naval_planner_dirty
\t\t\t\t}
\t\t\t}
\t\t\teu5ab_schedule_governor_recalculation = yes
\t\t}
\t\telse_if = {
\t\t\tlimit = { var:eu5ab_global_governor_recommendations_enabled <= 0 NOT = { has_variable = eu5ab_governor_manual_run } }
\t\t\tcmf_remove_alert = { alert = eu5ab_local_governor_available_alert }
\t\t\tcmf_remove_alert = { alert = eu5ab_naval_governor_available_alert }
\t\t\teu5ab_governor_clear_local_migration = yes
\t\t\tremove_variable = eu5ab_layout_confirmation_streak
\t\t\teu5ab_governor_clear_naval_migration = yes
\t\t\tremove_variable = eu5ab_local_has_new_recommendation
\t\t\tremove_variable = eu5ab_naval_has_new_recommendation
\t\t\tremove_variable = eu5ab_local_notified_target
\t\t\tremove_variable = eu5ab_naval_notified_target
\t\t}
\t}
}

eu5ab_schedule_governor_recalculation = {
\tif = {
\t\tlimit = {
\t\t\tvar:eu5ab_global_governor_recommendations_enabled > 0
\t\t\tNOT = { has_variable = eu5ab_governor_recalculation_scheduled }
\t\t}
\t\tset_variable = eu5ab_governor_recalculation_scheduled
\t\ttrigger_event_silently = { id = eu5ab_governor.1 days = 1 }
\t}
}

# Manual refresh runs while the game is paused. If a periodic refresh is already
# queued, its event is consumed on arrival so the expensive scan is not repeated.
eu5ab_governor_manual_recalculation = {
\teu5ab_governor_ensure_planner_schema = yes
\tif = {
\t\tlimit = { is_human = yes }
\t\tif = { limit = { has_variable = eu5ab_governor_scan_active } eu5ab_layout_abort = yes }
\t\t# Refresh settings before any eligibility/scoring gate. A one-shot manual
\t\t# job does not change the user's automatic-refresh preferences.
\t\teu5ab_sync_cmm_settings = yes
\t\tset_variable = eu5ab_governor_manual_run
\t\tset_variable = eu5ab_governor_manual_realert
\t\tremove_variable = eu5ab_governor_resume_manual
\t\tset_variable = eu5ab_governor_window_requested
\t\teu5ab_layout_clear_published_results = yes
\t\teu5ab_governor_clear_local_migration = yes
\t\teu5ab_governor_clear_naval_migration = yes
\t\tif = {
\t\t\tlimit = { has_variable = eu5ab_governor_recalculation_scheduled }
\t\t\tset_variable = eu5ab_governor_skip_next_scheduled_event
\t\t}
\t\teu5ab_governor_run_recalculation_now = yes
\t\t# A click returns a complete result (or an explicit failure), never a
\t\t# background layout job. Automatic refreshes still use bounded GUI pulses.
\t\teu5ab_layout_finish_manual = yes
\t\teu5ab_naval_planner_manual_recalculation = yes
\t\tremove_variable = eu5ab_governor_manual_realert
\t}
}

eu5ab_governor_run_recalculation_now = {
\tif = {
\t\tlimit = {
\t\t\tis_human = yes
\t\t\tOR = { var:eu5ab_global_governor_recommendations_enabled > 0 has_variable = eu5ab_governor_manual_run }
\t\t\tNOT = { has_variable = eu5ab_governor_scan_active }
\t\t}
\t\tset_variable = eu5ab_governor_scan_active
\t\teu5ab_recalculate_governor_recommendations = yes
\t}
\telse_if = {
\t\tlimit = { has_variable = eu5ab_governor_scan_active }
\t\tset_variable = eu5ab_governor_dirty
\t}
}

eu5ab_governor_clear_country_results = {
\tremove_variable = eu5ab_gov_result_road_tier
\tremove_variable = eu5ab_governor_queue_exhausted
\tremove_variable = eu5ab_local_has_new_recommendation
\t# Naval results belong to their independent planner.
\tset_variable = { name = eu5ab_governor_total_value value = 0 }
\tremove_variable = eu5ab_local_top_1
\tremove_variable = eu5ab_local_top_2
\tremove_variable = eu5ab_local_top_3
\tclear_variable_list = eu5ab_local_top_1_list
\tclear_variable_list = eu5ab_local_top_2_list
\tclear_variable_list = eu5ab_local_top_3_list
\tremove_variable = eu5ab_local_top_1_score
\tremove_variable = eu5ab_local_top_1_site_gain
\tremove_variable = eu5ab_local_top_1_surrounding_gain
\tremove_variable = eu5ab_local_top_1_coverage
\tremove_variable = eu5ab_local_top_2_score
\tremove_variable = eu5ab_local_top_2_site_gain
\tremove_variable = eu5ab_local_top_2_surrounding_gain
\tremove_variable = eu5ab_local_top_2_coverage
\tremove_variable = eu5ab_local_top_3_score
\tremove_variable = eu5ab_local_top_3_site_gain
\tremove_variable = eu5ab_local_top_3_surrounding_gain
\tremove_variable = eu5ab_local_top_3_coverage
\tclear_variable_list = eu5ab_gov_eval_locations
}

eu5ab_governor_clear_naval_results = {
\tremove_variable = eu5ab_naval_has_new_recommendation
\tremove_variable = eu5ab_naval_top_1
\tremove_variable = eu5ab_naval_top_2
\tremove_variable = eu5ab_naval_top_3
\tclear_variable_list = eu5ab_naval_top_1_list
\tclear_variable_list = eu5ab_naval_top_2_list
\tclear_variable_list = eu5ab_naval_top_3_list
\tremove_variable = eu5ab_naval_top_1_score
\tremove_variable = eu5ab_naval_top_1_site_gain
\tremove_variable = eu5ab_naval_top_1_surrounding_gain
\tremove_variable = eu5ab_naval_top_1_coverage
\tremove_variable = eu5ab_naval_top_2_score
\tremove_variable = eu5ab_naval_top_2_site_gain
\tremove_variable = eu5ab_naval_top_2_surrounding_gain
\tremove_variable = eu5ab_naval_top_2_coverage
\tremove_variable = eu5ab_naval_top_3_score
\tremove_variable = eu5ab_naval_top_3_site_gain
\tremove_variable = eu5ab_naval_top_3_surrounding_gain
\tremove_variable = eu5ab_naval_top_3_coverage
}

eu5ab_governor_clear_location_cache = {
\tremove_variable = eu5ab_gov_planned_proximity
\tremove_variable = eu5ab_gov_cached_local_speed
\tremove_variable = eu5ab_gov_cached_topography
\tremove_variable = eu5ab_gov_cached_topography_impact
\tremove_variable = eu5ab_gov_cached_vegetation
\tremove_variable = eu5ab_gov_node_value
\tremove_variable = eu5ab_gov_node_demand
\tremove_variable = eu5ab_gov_cached_population
\tremove_variable = eu5ab_gov_cached_potential_tax_base
\tremove_variable = eu5ab_gov_cached_development
\tremove_variable = eu5ab_gov_edge_cost_factor
\tremove_variable = eu5ab_gov_planned_road_cost
\tremove_variable = eu5ab_gov_road_edge_base_cost
\tremove_variable = eu5ab_gov_land_edge_base_cost
\tremove_variable = eu5ab_gov_cached_old_proximity
\tremove_variable = eu5ab_gov_cached_old_control
\tremove_variable = eu5ab_gov_cached_old_max_control
\tremove_variable = eu5ab_local_cheap_score
\tremove_variable = eu5ab_local_score
\tremove_variable = eu5ab_local_site_gain
\tremove_variable = eu5ab_local_surrounding_gain
\tremove_variable = eu5ab_local_coverage
\tremove_variable = eu5ab_gov_in_queue
\tremove_variable = eu5ab_gov_queue_next
\tremove_variable = eu5ab_gov_visit_generation
\tremove_variable = eu5ab_gov_predicted
\tremove_variable = eu5ab_gov_depth
}

eu5ab_governor_prepare_location_value = {
\teu5ab_prepare_strait_connections = yes
\tset_variable = { name = eu5ab_gov_cached_local_speed value = modifier:local_distance_from_capital_speed_propagation }
\tset_variable = { name = eu5ab_gov_cached_topography value = eu5ab_governor_topography_penalty }
\tset_variable = { name = eu5ab_gov_cached_topography_impact value = eu5ab_governor_topography_impact }
\tset_variable = { name = eu5ab_gov_cached_vegetation value = eu5ab_governor_vegetation_penalty }
\tset_variable = { name = eu5ab_gov_cached_population value = population }
\tset_variable = { name = eu5ab_gov_cached_potential_tax_base value = eu5ab_governor_potential_tax_base }
\tset_variable = { name = eu5ab_gov_cached_development value = development }
\tset_variable = { name = eu5ab_gov_node_value value = eu5ab_governor_cached_location_value }
\tset_variable = { name = eu5ab_gov_edge_cost_factor value = eu5ab_governor_edge_cost_factor }
\tset_variable = { name = eu5ab_gov_road_edge_base_cost value = eu5ab_governor_road_edge_base_cost }
\tset_variable = { name = eu5ab_gov_planned_road_cost value = eu5ab_governor_planned_road_cost }
\tset_variable = { name = eu5ab_gov_land_edge_base_cost value = eu5ab_governor_land_edge_base_cost }
\tset_variable = { name = eu5ab_gov_cached_old_proximity value = proximity }
\tset_variable = { name = eu5ab_gov_cached_old_control value = local_control }
\tset_variable = { name = eu5ab_gov_cached_old_max_control value = max_control }
\tset_variable = {
\t\tname = eu5ab_gov_node_demand
\t\tvalue = {
\t\t\tvalue = 80
\t\t\tsubtract = proximity
\t\t\tmin = 0
\t\t\tdivide = 100
\t\t\tmultiply = var:eu5ab_gov_node_value
\t\t}
\t}
\troot = {
\t\tchange_variable = { name = eu5ab_governor_total_value add = prev.var:eu5ab_gov_node_value }
\t}
}

eu5ab_governor_queue_enqueue = {
\tsave_temporary_scope_as = eu5ab_gov_queue_new
\tif = {
\t\tlimit = { NOT = { has_variable = eu5ab_gov_in_queue } }
\t\tset_variable = eu5ab_gov_in_queue
\t\tremove_variable = eu5ab_gov_queue_next
\t\troot = {
\t\t\tif = {
\t\t\t\tlimit = { has_variable = eu5ab_gov_queue_tail }
\t\t\t\tvar:eu5ab_gov_queue_tail = { set_variable = { name = eu5ab_gov_queue_next value = scope:eu5ab_gov_queue_new } }
\t\t\t\tset_variable = { name = eu5ab_gov_queue_tail value = scope:eu5ab_gov_queue_new }
\t\t\t}
\t\t\telse = {
\t\t\t\tset_variable = { name = eu5ab_gov_queue_head value = scope:eu5ab_gov_queue_new }
\t\t\t\tset_variable = { name = eu5ab_gov_queue_tail value = scope:eu5ab_gov_queue_new }
\t\t\t}
\t\t}
\t}
}

eu5ab_governor_queue_relax_one = {
\tif = {
\t\tlimit = { has_variable = eu5ab_gov_queue_head }
\t\tvar:eu5ab_gov_queue_head = { save_temporary_scope_as = eu5ab_gov_current }
\t\tscope:eu5ab_gov_current = {
\t\t\tif = {
\t\t\t\tlimit = { has_variable = eu5ab_gov_queue_next }
\t\t\t\tvar:eu5ab_gov_queue_next = { save_temporary_scope_as = eu5ab_gov_next }
\t\t\t\troot = { set_variable = { name = eu5ab_gov_queue_head value = scope:eu5ab_gov_next } }
\t\t\t}
\t\t\telse = { root = { remove_variable = eu5ab_gov_queue_head remove_variable = eu5ab_gov_queue_tail } }
\t\t\tremove_variable = eu5ab_gov_queue_next
\t\t\tremove_variable = eu5ab_gov_in_queue
\t\t\tif = {
\t\t\t\tlimit = { OR = { root.var:eu5ab_gov_eval_kind != 1 var:eu5ab_gov_depth < 6 } var:eu5ab_gov_predicted > 0 }
\t\t\t\tsave_temporary_scope_as = eu5ab_gov_edge_from
\t\t\t\tevery_neighbor_location = {
\t\t\t\t\tlimit = {
\t\t\t\t\t\tis_ownable = yes
\t\t\t\t\t\towner ?= root
\t\t\t\t\t\tOR = {
\t\t\t\t\t\t\troot.var:eu5ab_gov_eval_kind = 2
\t\t\t\t\t\t\tNOT = { eu5ab_is_strait_connection_to = { target = scope:eu5ab_gov_edge_from } }
\t\t\t\t\t\t}
\t\t\t\t\t}
\t\t\t\t\tif = {
\t\t\t\t\t\tlimit = { NOT = { has_variable = eu5ab_gov_visit_generation } }
\t\t\t\t\t\tset_variable = { name = eu5ab_gov_visit_generation value = -1 }
\t\t\t\t\t}
\t\t\t\t\tif = {
\t\t\t\t\t\tlimit = { var:eu5ab_gov_visit_generation != root.var:eu5ab_gov_eval_generation }
\t\t\t\t\t\tset_variable = { name = eu5ab_gov_visit_generation value = root.var:eu5ab_gov_eval_generation }
\t\t\t\t\t\tset_variable = { name = eu5ab_gov_predicted value = 0 }
\t\t\t\t\t\tset_variable = { name = eu5ab_gov_depth value = 99 }
\t\t\t\t\t\tsave_temporary_scope_as = eu5ab_gov_newly_visited
\t\t\t\t\t\troot = { add_to_variable_list = { name = eu5ab_gov_eval_locations target = scope:eu5ab_gov_newly_visited } }
\t\t\t\t\t}
\t\t\t\t\tif = {
\t\t\t\t\t\tlimit = { root.var:eu5ab_gov_eval_kind = 2 }
\t\t\t\t\t\tset_local_variable = { name = eu5ab_gov_relaxed value = eu5ab_governor_land_edge_prediction }
\t\t\t\t\t}
\t\t\t\t\telse = { set_local_variable = { name = eu5ab_gov_relaxed value = eu5ab_governor_known_land_edge_prediction } }
\t\t\t\t\tif = {
\t\t\t\t\t\tlimit = { local_var:eu5ab_gov_relaxed > var:eu5ab_gov_predicted }
\t\t\t\t\t\tset_variable = { name = eu5ab_gov_predicted value = local_var:eu5ab_gov_relaxed }
\t\t\t\t\t\tset_variable = { name = eu5ab_gov_depth value = { value = scope:eu5ab_gov_edge_from.var:eu5ab_gov_depth add = 1 } }
\t\t\t\t\t\teu5ab_governor_queue_enqueue = yes
\t\t\t\t\t}
\t\t\t\t\tremove_local_variable = eu5ab_gov_relaxed
\t\t\t\t}
{sync_lake_relaxation}
\t\t\t}
\t\t}
\t}
}

eu5ab_governor_evaluate_candidate = {
\tsave_temporary_scope_as = eu5ab_gov_evaluated_candidate
\troot = {
\t\tremove_variable = eu5ab_gov_queue_head
\t\tremove_variable = eu5ab_gov_queue_tail
\t\tclear_variable_list = eu5ab_gov_eval_locations
\t\tif = {
\t\t\tlimit = { NOT = { has_variable = eu5ab_gov_eval_generation } }
\t\t\tset_variable = { name = eu5ab_gov_eval_generation value = 0 }
\t\t}
\t\tchange_variable = { name = eu5ab_gov_eval_generation add = 1 }
\t\tset_variable = { name = eu5ab_gov_eval_site_gain value = 0 }
\t\tset_variable = { name = eu5ab_gov_eval_surrounding_gain value = 0 }
\t\tset_variable = { name = eu5ab_gov_eval_value value = 0 }
\t\tset_variable = { name = eu5ab_gov_eval_coverage value = 0 }
\t}
\tset_variable = { name = eu5ab_gov_visit_generation value = root.var:eu5ab_gov_eval_generation }
\tset_variable = { name = eu5ab_gov_predicted value = { value = eu5ab_governor_current_proximity_source add = 80 min = 0 max = 100 } }
\tset_variable = { name = eu5ab_gov_depth value = 0 }
\troot = { add_to_variable_list = { name = eu5ab_gov_eval_locations target = scope:eu5ab_gov_evaluated_candidate } }
\teu5ab_governor_queue_enqueue = yes
\troot = {
\t\twhile = {
\t\t\tlimit = { has_variable = eu5ab_gov_queue_head }
\t\t\tcount = { value = num_locations multiply = 4 min = 100 }
\t\t\teu5ab_governor_queue_relax_one = yes
\t\t}
\t\tif = { limit = { has_variable = eu5ab_gov_queue_head } set_variable = eu5ab_governor_queue_exhausted }
\t\tevery_in_list = {
\t\t\tvariable = eu5ab_gov_eval_locations
\t\t\tif = {
\t\t\t\tlimit = { var:eu5ab_gov_visit_generation = root.var:eu5ab_gov_eval_generation }
\t\t\t\tif = {
\t\t\t\t\tlimit = { var:eu5ab_gov_predicted > eu5ab_governor_comparison_proximity }
\t\t\t\t\tif = {
\t\t\t\t\t\tlimit = { this ?= scope:eu5ab_gov_evaluated_candidate }
\t\t\t\t\t\troot = { change_variable = { name = eu5ab_gov_eval_site_gain add = prev.eu5ab_governor_node_marginal_gain } }
\t\t\t\t\t}
\t\t\t\t\telse = {
\t\t\t\t\t\troot = { change_variable = { name = eu5ab_gov_eval_surrounding_gain add = prev.eu5ab_governor_node_marginal_gain } }
\t\t\t\t\t}
\t\t\t\t\troot = {
\t\t\t\t\t\tchange_variable = { name = eu5ab_gov_eval_value add = prev.var:eu5ab_gov_node_value }
\t\t\t\t\t\tchange_variable = { name = eu5ab_gov_eval_coverage add = 1 }
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t\tremove_variable = eu5ab_gov_in_queue
\t\t\tremove_variable = eu5ab_gov_queue_next
\t\t}
\t\tclear_variable_list = eu5ab_gov_eval_locations
\t}
\t# Quantize each displayed component first so the one-decimal card values
\t# add exactly to the displayed overall score.
\tset_variable = {
\t\tname = eu5ab_gov_eval_result_site_gain
\t\tvalue = { value = root.var:eu5ab_gov_eval_site_gain multiply = 10 round = yes divide = 10 }
\t}
\tset_variable = {
\t\tname = eu5ab_gov_eval_result_surrounding_gain
\t\tvalue = { value = root.var:eu5ab_gov_eval_surrounding_gain multiply = 10 round = yes divide = 10 }
\t}
\tset_variable = {
\t\tname = eu5ab_gov_eval_result_gain
\t\tvalue = { value = var:eu5ab_gov_eval_result_site_gain add = var:eu5ab_gov_eval_result_surrounding_gain }
\t}
\tset_variable = { name = eu5ab_gov_eval_result_coverage value = root.var:eu5ab_gov_eval_coverage }
\troot = {
\t\tremove_variable = eu5ab_gov_queue_head
\t\tremove_variable = eu5ab_gov_queue_tail
\t\tremove_variable = eu5ab_gov_eval_site_gain
\t\tremove_variable = eu5ab_gov_eval_surrounding_gain
\t\tremove_variable = eu5ab_gov_eval_value
\t\tremove_variable = eu5ab_gov_eval_coverage
\t}
}

eu5ab_governor_prepare_local_cheap_score = {
\tset_variable = { name = eu5ab_local_cheap_score value = var:eu5ab_gov_node_demand }
\tsave_temporary_scope_as = eu5ab_local_cheap_candidate
\tevery_neighbor_location = {
\t\tlimit = { is_ownable = yes owner ?= root NOT = { eu5ab_is_strait_connection_to = { target = scope:eu5ab_local_cheap_candidate } } }
\t\tscope:eu5ab_local_cheap_candidate = {
\t\t\tchange_variable = { name = eu5ab_local_cheap_score add = { value = prev.var:eu5ab_gov_node_demand multiply = 0.65 } }
\t\t}
\t}
}

eu5ab_governor_evaluate_local_candidate = {
\troot = { set_variable = { name = eu5ab_gov_eval_kind value = 1 } }
\teu5ab_governor_evaluate_candidate = yes
\tset_variable = { name = eu5ab_local_site_gain value = var:eu5ab_gov_eval_result_site_gain }
\tset_variable = { name = eu5ab_local_surrounding_gain value = var:eu5ab_gov_eval_result_surrounding_gain }
\tset_variable = { name = eu5ab_local_coverage value = var:eu5ab_gov_eval_result_coverage }
\tset_variable = { name = eu5ab_local_score value = var:eu5ab_gov_eval_result_gain }
\tremove_variable = eu5ab_gov_eval_result_gain
\tremove_variable = eu5ab_gov_eval_result_site_gain
\tremove_variable = eu5ab_gov_eval_result_surrounding_gain
\tremove_variable = eu5ab_gov_eval_result_coverage
}

# Store one Local Governor candidate in the next country-level Top 3 slot.
eu5ab_governor_store_local_rank = {
\tsave_temporary_scope_as = eu5ab_local_ranked_candidate
\troot = {
\t\tif = {
\t\t\tlimit = { var:eu5ab_gov_rank_cursor = 0 }
\t\t\tset_variable = { name = eu5ab_local_top_1 value = scope:eu5ab_local_ranked_candidate }
\t\t\tadd_to_variable_list = { name = eu5ab_local_top_1_list target = scope:eu5ab_local_ranked_candidate }
\t\t\tset_variable = { name = eu5ab_local_top_1_score value = scope:eu5ab_local_ranked_candidate.var:eu5ab_local_score }
\t\t\tset_variable = { name = eu5ab_local_top_1_site_gain value = scope:eu5ab_local_ranked_candidate.var:eu5ab_local_site_gain }
\t\t\tset_variable = { name = eu5ab_local_top_1_surrounding_gain value = scope:eu5ab_local_ranked_candidate.var:eu5ab_local_surrounding_gain }
\t\t\tset_variable = { name = eu5ab_local_top_1_coverage value = scope:eu5ab_local_ranked_candidate.var:eu5ab_local_coverage }
\t\t}
\t\telse_if = {
\t\t\tlimit = { var:eu5ab_gov_rank_cursor = 1 }
\t\t\tset_variable = { name = eu5ab_local_top_2 value = scope:eu5ab_local_ranked_candidate }
\t\t\tadd_to_variable_list = { name = eu5ab_local_top_2_list target = scope:eu5ab_local_ranked_candidate }
\t\t\tset_variable = { name = eu5ab_local_top_2_score value = scope:eu5ab_local_ranked_candidate.var:eu5ab_local_score }
\t\t\tset_variable = { name = eu5ab_local_top_2_site_gain value = scope:eu5ab_local_ranked_candidate.var:eu5ab_local_site_gain }
\t\t\tset_variable = { name = eu5ab_local_top_2_surrounding_gain value = scope:eu5ab_local_ranked_candidate.var:eu5ab_local_surrounding_gain }
\t\t\tset_variable = { name = eu5ab_local_top_2_coverage value = scope:eu5ab_local_ranked_candidate.var:eu5ab_local_coverage }
\t\t}
\t\telse = {
\t\t\tset_variable = { name = eu5ab_local_top_3 value = scope:eu5ab_local_ranked_candidate }
\t\t\tadd_to_variable_list = { name = eu5ab_local_top_3_list target = scope:eu5ab_local_ranked_candidate }
\t\t\tset_variable = { name = eu5ab_local_top_3_score value = scope:eu5ab_local_ranked_candidate.var:eu5ab_local_score }
\t\t\tset_variable = { name = eu5ab_local_top_3_site_gain value = scope:eu5ab_local_ranked_candidate.var:eu5ab_local_site_gain }
\t\t\tset_variable = { name = eu5ab_local_top_3_surrounding_gain value = scope:eu5ab_local_ranked_candidate.var:eu5ab_local_surrounding_gain }
\t\t\tset_variable = { name = eu5ab_local_top_3_coverage value = scope:eu5ab_local_ranked_candidate.var:eu5ab_local_coverage }
\t\t}
\t\tchange_variable = { name = eu5ab_gov_rank_cursor add = 1 }
\t}
}

eu5ab_governor_rank_local_results = {
\tset_variable = { name = eu5ab_gov_rank_cursor value = 0 }
\tordered_owned_location = {
\t\tlimit = {
\t\t\teu5ab_local_governor_candidate = yes
\t\t\thas_variable = eu5ab_local_score
\t\t\tvar:eu5ab_local_score > 0
\t\t\troot = { NOT = { has_variable = eu5ab_governor_queue_exhausted } NOT = { has_variable = eu5ab_governor_baseline_failed } }
\t\t}
\t\torder_by = var:eu5ab_local_score
\t\tmax = 3
\t\tcheck_range_bounds = no
\t\teu5ab_governor_store_local_rank = yes
\t}
\tremove_variable = eu5ab_gov_rank_cursor
}

eu5ab_governor_evaluate_local_alerts = {
\tremove_variable = eu5ab_local_has_new_recommendation
\tif = {
\t\tlimit = { eu5ab_fresh_local_governor_slot_available = yes }
\t\tif = {
\t\t\tlimit = {
\t\t\t\thas_variable = eu5ab_local_top_1
\t\t\t\tvar:eu5ab_local_top_1_score >= eu5ab_governor_new_recommendation_threshold
\t\t\t\t# The vanilla can-build trigger requires scope:actor and is invalid in
\t\t\t\t# this background country effect. Slot capacity is checked above; this
\t\t\t\t# rechecks the actor-independent location conditions instead.
\t\t\t\tvar:eu5ab_local_top_1 = { eu5ab_local_governor_candidate = yes }
\t\t\t}
\t\t\tset_variable = eu5ab_local_has_new_recommendation
\t\t\tif = {
\t\t\t\tlimit = {
\t\t\t\t\tOR = {
\t\t\t\t\t\thas_variable = eu5ab_governor_manual_realert
\t\t\t\t\t\tNOT = { has_variable = eu5ab_local_notified_target }
\t\t\t\t\t\tvar:eu5ab_local_notified_target != var:eu5ab_local_top_1
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tcmf_remove_alert = { alert = eu5ab_local_governor_available_alert }
\t\t\t\tset_variable = { name = eu5ab_local_notified_target value = var:eu5ab_local_top_1 }
\t\t\t\tcmf_show_alert = { alert = eu5ab_local_governor_available_alert }
\t\t\t}
\t\t}
\t\telse = {
\t\t\tcmf_remove_alert = { alert = eu5ab_local_governor_available_alert }
\t\t\tremove_variable = eu5ab_local_notified_target
\t\t}
\t}
\telse = {
\t\tcmf_remove_alert = { alert = eu5ab_local_governor_available_alert }
\t\tremove_variable = eu5ab_local_notified_target
\t\t# Local migration is published by the complete-layout planner.
\t}
}


# Country-scope master pass. It is event driven when an exposed on-action is
# available and periodically repeated to catch road-level/global modifier
# changes without a native invalidation hook, including expiring effects.
eu5ab_governor_snapshot_local_slot_state = {
\t# All four native types have one level. In-progress buildings occupy slots
\t# but do not add a completed source. Keep raw counts for diagnostics.
\tset_variable = { name = eu5ab_gov_fresh_local_capacity value = effective_num_local_governors }
\tset_variable = { name = eu5ab_gov_fresh_local_occupied value = 0 }
\tset_variable = { name = eu5ab_gov_fresh_lieutenancies value = 0 }
\tset_variable = { name = eu5ab_gov_fresh_itinerant_seats value = 0 }
\tset_variable = { name = eu5ab_gov_fresh_kings_manors value = 0 }
\tevery_owned_location = {
\t\tif = {
\t\t\tlimit = { OR = { has_building = building_type:local_governor any_buildings_in_location = { building_type = building_type:local_governor building_levels_under_construction > 0 } } }
\t\t\troot = { change_variable = { name = eu5ab_gov_fresh_local_occupied add = 1 } }
\t\t}
\t\tif = {
\t\t\tlimit = { OR = { has_building = building_type:lieutenancy any_buildings_in_location = { building_type = building_type:lieutenancy building_levels_under_construction > 0 } } }
\t\t\troot = { change_variable = { name = eu5ab_gov_fresh_lieutenancies add = 1 } }
\t\t}
\t\tif = {
\t\t\tlimit = { OR = { has_building = building_type:itinerant_court_seat any_buildings_in_location = { building_type = building_type:itinerant_court_seat building_levels_under_construction > 0 } } }
\t\t\troot = { change_variable = { name = eu5ab_gov_fresh_itinerant_seats add = 1 } }
\t\t}
\t\tif = {
\t\t\tlimit = { OR = { has_building = building_type:kings_manor any_buildings_in_location = { building_type = building_type:kings_manor building_levels_under_construction > 0 } } }
\t\t\troot = { change_variable = { name = eu5ab_gov_fresh_kings_manors add = 1 } }
\t\t}
\t}
}

eu5ab_governor_snapshot_local_diagnostics = {
\t# Preserve native inputs and synchronous outcomes before layout_begin clears
\t# the location caches. These observations never drive recommendation rules.
\tset_variable = { name = eu5ab_gov_sync_capacity value = effective_num_local_governors }
\tset_variable = { name = eu5ab_gov_sync_occupied value = total_building_levels_including_construction:local_governor }
\tset_variable = { name = eu5ab_gov_sync_lieutenancies value = total_building_levels_including_construction:lieutenancy }
\tset_variable = { name = eu5ab_gov_sync_other_slots value = eu5ab_governor_local_other_slots }
\tset_variable = { name = eu5ab_gov_sync_threshold value = eu5ab_governor_new_recommendation_threshold }
\tset_variable = { name = eu5ab_gov_sync_slot_available value = 0 }
\tif = { limit = { eu5ab_local_governor_slot_available = yes } set_variable = { name = eu5ab_gov_sync_slot_available value = 1 } }
\tset_variable = { name = eu5ab_gov_sync_fresh_occupied value = var:eu5ab_gov_fresh_local_occupied }
\tset_variable = { name = eu5ab_gov_sync_fresh_lieutenancies value = var:eu5ab_gov_fresh_lieutenancies }
\tset_variable = { name = eu5ab_gov_sync_fresh_other_slots value = eu5ab_governor_fresh_local_other_slots }
\tset_variable = { name = eu5ab_gov_sync_fresh_slot_available value = 0 }
\tif = { limit = { eu5ab_fresh_local_governor_slot_available = yes } set_variable = { name = eu5ab_gov_sync_fresh_slot_available value = 1 } }
\tset_variable = { name = eu5ab_gov_sync_slot_cache_mismatch value = 0 }
\tif = { limit = { var:eu5ab_gov_sync_slot_available != var:eu5ab_gov_sync_fresh_slot_available } set_variable = { name = eu5ab_gov_sync_slot_cache_mismatch value = 1 } }
\tset_variable = { name = eu5ab_gov_sync_baseline_failed value = 0 }
\tif = { limit = { has_variable = eu5ab_governor_baseline_failed } set_variable = { name = eu5ab_gov_sync_baseline_failed value = 1 } }
\tset_variable = { name = eu5ab_gov_sync_queue_exhausted value = 0 }
\tif = { limit = { has_variable = eu5ab_governor_queue_exhausted } set_variable = { name = eu5ab_gov_sync_queue_exhausted value = 1 } }
\tset_variable = { name = eu5ab_gov_sync_candidates value = 0 }
\tset_variable = { name = eu5ab_gov_sync_shortlisted value = 0 }
\tevery_owned_location = {
\t\tif = { limit = { eu5ab_local_governor_candidate = yes } root = { change_variable = { name = eu5ab_gov_sync_candidates add = 1 } } }
\t\tif = { limit = { has_variable = eu5ab_local_score } root = { change_variable = { name = eu5ab_gov_sync_shortlisted add = 1 } } }
\t}
}

eu5ab_governor_refresh_other_recommendations = {
\tif = {
\t\tlimit = { is_human = yes OR = { var:eu5ab_global_governor_recommendations_enabled > 0 has_variable = eu5ab_governor_manual_run } }
\t\tif = { limit = { NOT = { has_variable = eu5ab_gov_sync_runs } } set_variable = { name = eu5ab_gov_sync_runs value = 0 } }
\t\tchange_variable = { name = eu5ab_gov_sync_runs add = 1 }
\t\tset_variable = { name = eu5ab_gov_sync_stage value = 1 }
\t\teu5ab_governor_clear_country_results = yes
\t\teu5ab_governor_snapshot_local_slot_state = yes
\t\teu5ab_governor_snapshot_transport = yes
\t\tremove_variable = eu5ab_governor_baseline_failed
\t\tevery_owned_location = { eu5ab_governor_clear_location_cache = yes }
\t\tevery_owned_location = { eu5ab_governor_prepare_location_value = yes }
\t\teu5ab_governor_prepare_planned_baseline = yes
\t\tset_variable = { name = eu5ab_gov_sync_stage value = 2 }

\t\t# Local Governor: all candidates get a cheap score; only the best eight
\t\t# receive a bounded counterfactual propagation. Full-slot relocation is
\t\t# evaluated separately by removing each old source before adding a new one.
\t\tevery_owned_location = {
\t\t\tlimit = { eu5ab_local_governor_candidate = yes root = { eu5ab_fresh_local_governor_slot_available = yes NOT = { has_variable = eu5ab_governor_baseline_failed } } }
\t\t\teu5ab_governor_prepare_local_cheap_score = yes
\t\t}
\t\tordered_owned_location = {
\t\t\tlimit = { has_variable = eu5ab_local_cheap_score }
\t\t\torder_by = var:eu5ab_local_cheap_score
\t\t\tmax = 8
\t\t\tcheck_range_bounds = no
\t\t\teu5ab_governor_evaluate_local_candidate = yes
\t\t}
\t\teu5ab_governor_rank_local_results = yes
\t\teu5ab_governor_snapshot_local_diagnostics = yes
\t\tset_variable = { name = eu5ab_gov_sync_stage value = 3 }
\t\t# Preserve the completed road label before layout work resets scratch data.
\t\tif = {
\t\t\tlimit = { NOT = { has_variable = eu5ab_governor_baseline_failed } NOT = { has_variable = eu5ab_governor_queue_exhausted } }
\t\t\tset_variable = { name = eu5ab_gov_result_road_tier value = var:eu5ab_gov_transport_road_tier }
\t\t}

\t\teu5ab_governor_evaluate_local_alerts = yes
\t\t# Published status is independent of the subsequent layout worker cache.
\t\tset_variable = { name = eu5ab_gov_sync_status value = 1 }
\t\tif = { limit = { eu5ab_fresh_local_governor_slot_available = yes } set_variable = { name = eu5ab_gov_sync_status value = 2 } }
\t\tif = { limit = { var:eu5ab_gov_sync_shortlisted > 0 } set_variable = { name = eu5ab_gov_sync_status value = 3 } }
\t\tif = { limit = { has_variable = eu5ab_local_has_new_recommendation } set_variable = { name = eu5ab_gov_sync_status value = 5 } }
\t\tif = { limit = { OR = { var:eu5ab_gov_sync_baseline_failed > 0 var:eu5ab_gov_sync_queue_exhausted > 0 } } set_variable = { name = eu5ab_gov_sync_status value = 4 } }
\t\tset_variable = { name = eu5ab_gov_sync_stage value = 4 }
\t\tif = {
\t\t\tlimit = { NOT = { has_variable = eu5ab_governor_baseline_failed } NOT = { has_variable = eu5ab_governor_queue_exhausted } }
\t\t\tset_variable = { name = eu5ab_gov_result_road_tier value = var:eu5ab_gov_transport_road_tier }
\t\t}
\t\tset_variable = { name = eu5ab_governor_last_run_year value = current_year }
\t\tset_variable = { name = eu5ab_governor_months_since_refresh value = 0 }
\t\tremove_variable = eu5ab_governor_dirty
\t\tremove_variable = eu5ab_gov_eval_kind
\t\tremove_variable = eu5ab_gov_eval_generation
\t}
}
"""
    effects = effects.replace("{sync_lake_relaxation}", render_lake_relaxation(layout=False))
    effects += render_transport_effects()
    effects += """
# Both manual buttons and the scheduled event call this same pipeline.
eu5ab_recalculate_governor_recommendations = {
\teu5ab_governor_refresh_other_recommendations = yes
\tif = { limit = { var:eu5ab_global_governor_relocation_enabled > 0 OR = { var:eu5ab_global_governor_migration_enabled > 0 has_variable = eu5ab_governor_manual_run } } eu5ab_layout_begin = yes }
\telse = {
\t\t# The synchronous new-site pass is complete; no layout job was started.
\t\tremove_variable = eu5ab_governor_scan_active
\t\tremove_variable = eu5ab_governor_manual_run
\t\teu5ab_governor_apply_migration_settings = yes
\t}
}

eu5ab_governor_initialize_relocation_setting = {
\tif = {
\t\tlimit = { NOT = { is_key_in_variable_map = { name = cmm target = flag:eu5ab_regional_development__governor_relocation_enabled } } }
\t\tcmm_set_setting_value = { setting = eu5ab_regional_development__governor_relocation_enabled value = 1 }
\t}
}

eu5ab_governor_apply_migration_settings = {
\tif = {
\t\tlimit = { NOT = { var:eu5ab_global_governor_relocation_enabled > 0 } }
\t\teu5ab_governor_disable_migration = yes
\t\teu5ab_naval_planner_disable_migration = yes
\t}
\telse_if = {
\t\tlimit = { NOT = { var:eu5ab_global_governor_migration_enabled > 0 } NOT = { has_variable = eu5ab_governor_manual_run } }
\t\teu5ab_governor_stop_auto_migration = yes
\t\teu5ab_naval_planner_stop_auto_migration = yes
\t}
}

eu5ab_governor_stop_auto_migration = {
\t# Stopping periodic work must not hide the last completed/manual result.
\tif = {
\t\tlimit = { has_variable = eu5ab_governor_scan_active NOT = { has_variable = eu5ab_governor_manual_run } }
\t\teu5ab_layout_abort = yes
\t\tremove_variable = eu5ab_layout_failed
\t}
\tremove_variable = eu5ab_layout_confirmation_streak
}

eu5ab_governor_disable_migration = {
\tif = { limit = { has_variable = eu5ab_governor_scan_active } eu5ab_layout_abort = yes }
\tremove_variable = eu5ab_layout_failed
\tif = {
\t\tlimit = { OR = { has_variable = eu5ab_layout_has_results var:eu5ab_layout_result_count > 0 var:eu5ab_layout_candidate_count > 0 } }
\t\teu5ab_layout_clear_published_results = yes
\t}
\tremove_variable = eu5ab_layout_confirmation_streak
\teu5ab_governor_clear_local_migration = yes
\teu5ab_governor_clear_naval_migration = yes
}
"""
    insertion_point = effects.index("eu5ab_governor_evaluate_local_alerts = {")
    local_effects = (
        effects[:insertion_point]
        + _render_migration_cleanup_effects()
        + "\n\n"
        + effects[insertion_point:]
        + "\n" + render_layout_effects()
    )
    naval_effects = render_naval_effects(local_effects)
    local_effects = add_footprint_links(integrate_refresh(local_effects))
    return (render_connection_effects(bundled_straits() if straits is None else straits) + "\n" + local_effects + "\n" + naval_effects
            + "\n" + render_planner_schema_effects() + "\n" + render_scheduled_planners())
