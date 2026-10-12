"""Bilingual explanations of the RGO and workforce decision rules."""


def add_horizon_step_tooltips(values: dict[str, str], *, english: bool) -> None:
    """Match the RGO horizon gestures while retaining other settings' tooltips."""
    condition = "EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__rgo_job_fill_deadline_months')"
    native_ctrl_step = "[Multiply_CFixedPoint(Player.MakeScope.GetVariableFromVariableMap('cmm_step', MakeScopeFlag(Scope.GetFlagName)).GetValue, '(CFixedPoint)5')]"
    for direction, endpoint, verb in (
        ('increase', 'MAX', 'Increase by' if english else '增加'),
        ('decrease', 'MIN', 'Decrease by' if english else '减少'),
    ):
        shift_key = f'EU5AB_CMM_NUMERIC_{direction.upper()}_{endpoint}'
        previous = values[shift_key][1:-1]
        values[shift_key] = f"[SelectLocalization({condition}, 'eu5ab_cmm_shift_{direction}_120', {previous})]"
        values[f'EU5AB_CMM_NUMERIC_{direction.upper()}_5X'] = (
            f"[SelectLocalization({condition}, 'eu5ab_cmm_ctrl_{direction}_12', 'eu5ab_cmm_ctrl_{direction}_default')]"
        )
        values[f'eu5ab_cmm_shift_{direction}_120'] = f'{verb} 120 months' if english else f'{verb} 120 个月'
        values[f'eu5ab_cmm_ctrl_{direction}_12'] = f'{verb} 12 months' if english else f'{verb} 12 个月'
        values[f'eu5ab_cmm_ctrl_{direction}_default'] = f'{verb} {native_ctrl_step}'


CMM_ZH = {
    'automation__rgo_desc': '已有岗位满员后才考虑原产扩建。可选择是否预测新增岗位所需的劳动力。',
    'rgo_workforce_mode_name': '原产劳动力模式',
    'rgo_forced_relaxed_name': '原产模式：宽松（劳动力保护已关闭）',
    'rgo_forced_relaxed_desc': '不预测未来劳动力，现有岗位仍须满员；新增岗位暂时缺人只会降低建造优先级。',
    'rgo_workforce_mode_desc': '默认「宽松」。劳动力保护关闭时暂用「宽松」模式，当前缺工会降低优先级；重新开启后恢复所选模式。已有岗位始终须满员。',
    'rgo_workforce_mode_option_1_name': '宽松',
    'rgo_workforce_mode_option_1_desc': '参考游戏的自动扩建规则：已有岗位满员后，按价格、市场需求和预计增产判断，不预测新增岗位能否招满。劳动力保护开启时，不因新增岗位暂时缺人而降低优先级。',
    'rgo_workforce_mode_option_2_name': '考虑人口',
    'rgo_workforce_mode_option_2_desc': '现有岗位满员后，再估算期限内能够转职的合格人口；不足以填满新增一级岗位时暂停。',
    'rgo_job_fill_deadline_months_name': '原产人口预测期限（月）',
    'rgo_job_fill_deadline_months_desc': '在「考虑人口」模式下，只有预计能在设定期限内补齐新增岗位，才会扩建。默认 180 个月，可设为 0—1200 个月；设为 0 时只看当前可用劳动力。估算会考虑「机遇众多」、识字率和可转职人口，期限越长，与实际情况的偏差可能越大。点击增减 1 个月，按住 Ctrl 增减 12 个月，按住 Shift 增减 120 个月。',
    'rgo_job_fill_deadline_months_format': "[CMMV('eu5ab_regional_development__rgo_job_fill_deadline_months')]",
    'pause_low_workforce_desc': '开启后，普通建筑须有足够的预计劳动力，原产按所选模式判断。关闭后停止预测，原产暂用「宽松」模式；当前缺工只降低优先级，不单独阻止新增工程。原产已有岗位仍须满员。重新开启后恢复原产之前的模式。',
    'job_fill_deadline_months_name': '普通建筑劳动力预测期限（月）',
    'job_fill_deadline_months_desc': '普通建筑独立使用此期限，默认 12 个月，可设 0—240；0 只看当前合格空闲人口。原产考虑人口模式另设期限。预测按当前晋升速度估算，不保证未来能够填满。',
    'price_min_desc': '默认基础价的 80%。价格越低，项目越不优先；全部产出均不高于门槛时暂停建设，多种产出按产量和基础价综合判断。门槛设为 100% 或更高时，只判断是否超过门槛。已启用的食物紧急保障可放宽价格限制。',
    'price_max_desc': '默认 125%。价格超过基础价后逐步加分，达到参考值后封顶。例如设为 125% 时，价格 112.5% 加 70 分，125% 及以上加 140 分。参考值不高于 100% 时，价格超过基础价即加 140 分。',
}
CMM_EN = {
    'automation__rgo_desc': 'Consider RGO expansion once existing jobs are full. Choose whether to forecast workers for new jobs.',
    'rgo_workforce_mode_name': 'RGO Workforce Mode',
    'rgo_forced_relaxed_name': 'RGO Mode: Relaxed (Workforce Pausing Off)',
    'rgo_forced_relaxed_desc': 'No workforce forecast. Existing jobs must be full; shortages for new jobs only lower construction priority.',
    'rgo_workforce_mode_desc': 'Relaxed by default. Turning workforce protection off temporarily uses Relaxed mode and lowers priority for current worker shortages. Re-enabling restores the selected mode. Existing jobs must always be full.',
    'rgo_workforce_mode_option_1_name': 'Relaxed',
    'rgo_workforce_mode_option_1_desc': "Follows the game's general expansion rules: once existing jobs are full, assess prices, market needs, and expected output without forecasting new workers. With workforce protection on, shortages for new jobs do not lower priority.",
    'rgo_workforce_mode_option_2_name': 'Consider Population',
    'rgo_workforce_mode_option_2_desc': 'After checking full existing employment, estimate qualified promotions over the horizon. Pause if workers cannot fill the next level.',
    'rgo_job_fill_deadline_months_name': 'RGO Population Horizon (Months)',
    'rgo_job_fill_deadline_months_desc': 'In Consider Population mode, expansion requires enough workers to be expected within this period to fill the new jobs. Default: 180 months. Range: 0-1200; zero counts only currently available workers. The estimate accounts for Plenty of Opportunities, literacy and the population eligible to change jobs. Longer forecasts may differ more from actual results. Click to adjust by 1 month, hold Ctrl for 12 months, or Shift for 120 months.',
    'rgo_job_fill_deadline_months_format': "[CMMV('eu5ab_regional_development__rgo_job_fill_deadline_months')]",
    'pause_low_workforce_desc': 'When enabled, ordinary buildings need sufficient forecast workers; RGOs use their selected mode. Turning this off stops forecasts and temporarily uses Relaxed mode for RGOs. Current shortages lower priority without blocking new projects by themselves. Existing RGO jobs must still be full. Re-enabling restores the previous RGO mode.',
    'job_fill_deadline_months_name': 'Ordinary-Building Workforce Horizon (Months)',
    'job_fill_deadline_months_desc': 'Independent horizon for ordinary buildings: default 12 months, range 0-240. Zero counts only currently qualified idle workers. Population-aware RGOs use their separate horizon. Current promotion rates are an estimate, not a guarantee.',
    'price_min_desc': 'Default: 80% of base price. Lower prices reduce priority. Pause construction when all outputs are at or below the threshold; weight multiple outputs by quantity and base price. At 100% or above, only the threshold applies. Enabled food safeguards can waive price limits.',
    'price_max_desc': 'Default: 125%. Prices above base gradually add priority up to the reference. At a 125% reference, a price of 112.5% adds 70 points; 125% or more adds 140. If the reference is 100% or lower, any price above base adds 140.',
}
CMM_ZH = {'eu5ab_regional_development__' + k: v for k, v in CMM_ZH.items()}
CMM_EN = {'eu5ab_regional_development__' + k: v for k, v in CMM_EN.items()}

ZH = {
    'eu5ab_rgo_short_desc': '已有岗位须满员，默认「宽松」；可另选「考虑人口」预测新增岗位的劳动力。',
    'eu5ab_rgo_help': '已有原产岗位须满员。默认「宽松」模式不预测新增岗位；「考虑人口」要求在所设期限内预计有足够劳动力。\\n价格不高于最低值时暂停扩建，低价降低优先级，高价提高优先级；评分低于 0 的项目不开工。\\n本国同市场、同商品的普通建筑和原产共用增产限制，计入在建及完工后尚未实现的增产，也考虑已安排工程新增的原料需求。预计增产越接近「需求缺口加需求量的 10%」，追加建设越不优先；达到该数量后暂停追加。最后一级可超出，已有工程继续施工。\\n关闭劳动力保护后停止预测，当前缺工仍降低优先级。已启用的食物紧急保障可优先安排相关原产，并放宽价格和增产限制；已有岗位满员、适用的劳动力要求、预算及游戏建造条件仍须满足。',
    'eu5ab_workforce_help': '普通建筑默认预测 12 个月，原产「考虑人口」模式默认 180 个月。按当前晋升速度、当地与全国修正、「机遇众多」、识字率和可转职人口估算；未来迁入、速度变化及其他岗位竞争可能影响结果。\\n关闭劳动力保护后停止预测，当前缺工只降低优先级，不改变预计利润；食物紧急保障仍按设置生效。',
    'eu5ab_diag_rgo_fail_utilization_label': '现有原产岗位未满员',
    'eu5ab_diag_rgo_fail_market_need_label': '原产价格未超过最低门槛',
    'eu5ab_diag_rgo_fail_score_label': '原产扩建评分低于 0',
    'eu5ab_diag_rgo_fail_score_value': "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_rgo_fail_score').GetValue|0]",
    'eu5ab_diag_rgo_factors_label': '原产优先级影响',
    'eu5ab_diag_rgo_pending_label': '同商品待释放产能',
    'eu5ab_diag_rgo_fail_pending_data_label': '供需或待释放产能数据不全',
    'eu5ab_diag_rgo_fail_pending_limit_label': '待释放产能已达到额度',
    'eu5ab_diag_rgo_pending_location_label': '最近检查待释放额度的地点',
    'eu5ab_diag_rgo_pending_gap_label': '当前市场缺口',
    'eu5ab_diag_rgo_pending_quantity_label': '本国同商品待释放产能',
    'eu5ab_diag_rgo_pending_limit_label': '待释放产能额度',
    'eu5ab_diag_rgo_pending_factor_label': '预计增产影响',
    'eu5ab_diag_rgo_pending_state_label': '待释放额度检查',
    'eu5ab_diag_rgo_pending_state_1': '通过，仍须满足其他扩建条件',
    'eu5ab_diag_rgo_pending_state_2': '已达额度，暂停新增',
    'eu5ab_diag_rgo_pending_state_3': '数据不全，暂停新增',
    'eu5ab_diag_rgo_pending_state_4': '粮食紧急，豁免额度限制',
}
EN = {
    'eu5ab_rgo_short_desc': 'Existing jobs must be full. Relaxed is the default; choose Consider Population to forecast workers for new jobs.',
    'eu5ab_rgo_help': 'Existing RGO jobs must be full. Relaxed mode, the default, does not forecast new workers; Consider Population requires enough workers to be expected within the chosen period.\\nPrices at or below the minimum pause expansion. Low prices reduce priority and high prices raise it. Projects scoring below 0 do not start.\\nOwned ordinary buildings and RGOs producing the same good in the same market share an expansion limit. It includes output gains not yet realized from ongoing or completed projects, and accounts for new input demand from planned projects. Further construction becomes less preferred as expected gains approach the demand shortage plus 10% of demand. New starts pause at that amount. The final level may exceed it; existing projects continue.\\nTurning workforce protection off stops forecasts, but current shortages still lower priority. Enabled food safeguards can prioritize relevant RGOs and waive price and expansion limits. Full existing employment and applicable workforce, budget, and game construction requirements still apply.',
    'eu5ab_workforce_help': 'Ordinary buildings default to a 12-month forecast; RGOs in Consider Population mode use 180 months. Estimates use current promotion rates, local and national modifiers, Plenty of Opportunities, literacy, and eligible population. Migration, changing rates, and competing jobs may affect results.\\nTurning workforce protection off stops forecasts. Current shortages lower priority without changing predicted profit; food safeguards still apply as configured.',
    'eu5ab_diag_rgo_fail_utilization_label': 'Existing RGO Jobs Not Fully Staffed',
    'eu5ab_diag_rgo_fail_market_need_label': 'RGO Price At or Below Floor',
    'eu5ab_diag_rgo_fail_score_label': 'RGO Expansion Score Below 0',
    'eu5ab_diag_rgo_fail_score_value': ZH['eu5ab_diag_rgo_fail_score_value'],
    'eu5ab_diag_rgo_factors_label': 'RGO Priority Factors',
    'eu5ab_diag_rgo_pending_label': 'Same-Good Pending Output',
    'eu5ab_diag_rgo_fail_pending_data_label': 'Supply, Demand or Pending Output Unavailable',
    'eu5ab_diag_rgo_fail_pending_limit_label': 'Pending Output Reached Allowance',
    'eu5ab_diag_rgo_pending_location_label': 'Last Pending-Output Check Location',
    'eu5ab_diag_rgo_pending_gap_label': 'Current Market Shortage',
    'eu5ab_diag_rgo_pending_quantity_label': 'Owned Same-Good Pending Output',
    'eu5ab_diag_rgo_pending_limit_label': 'Pending-Output Allowance',
    'eu5ab_diag_rgo_pending_factor_label': 'Output Impact on Priority',
    'eu5ab_diag_rgo_pending_state_label': 'Pending-Output Check',
    'eu5ab_diag_rgo_pending_state_1': 'Passed; other expansion conditions still apply',
    'eu5ab_diag_rgo_pending_state_2': 'Allowance reached; new starts paused',
    'eu5ab_diag_rgo_pending_state_3': 'Incomplete data; new starts paused',
    'eu5ab_diag_rgo_pending_state_4': 'Food emergency; allowance waived',
}
for reason in ('data', 'limit'):
    key = f'eu5ab_diag_rgo_fail_pending_{reason}_value'
    ZH[key] = EN[key] = f"[GetPlayer.MakeScope.GetVariable('eu5ab_diag_rgo_fail_pending_{reason}').GetValue|0]"
for suffix in ('gap', 'quantity', 'limit', 'factor'):
    key = f'eu5ab_diag_rgo_pending_{suffix}_value'
    ZH[key] = EN[key] = f"[GetPlayer.MakeScope.GetVariable('eu5ab_diag_rgo_pending_{suffix}').GetValue|2]" + ('%' if suffix == 'factor' else '')
ZH['eu5ab_diag_rgo_pending_location_value'] = EN['eu5ab_diag_rgo_pending_location_value'] = "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_rgo_pending_location').GetLocation.GetName]"
for rank in range(1, 4):
    def field(suffix):
        return f"[GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_{rank}_rgo_{suffix}_factor').GetValue|0]%"
    ZH[f'eu5ab_diag_candidate_{rank}_rgo_factors_value'] = f'价格 {field("price")} · 待释放 {field("pending")} · 缺工 {field("labor")}'
    EN[f'eu5ab_diag_candidate_{rank}_rgo_factors_value'] = f'Price {field("price")} · Pending {field("pending")} · Workers {field("labor")}'
    def quantity(suffix):
        return f"[GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_{rank}_rgo_{suffix}').GetValue|2]"
    ZH[f'eu5ab_diag_candidate_{rank}_rgo_pending_value'] = f'缺口 {quantity("market_gap")} · 待释放 {quantity("pending_quantity")} / {quantity("pending_limit")}'
    EN[f'eu5ab_diag_candidate_{rank}_rgo_pending_value'] = f'Shortage {quantity("market_gap")} · Pending {quantity("pending_quantity")} / {quantity("pending_limit")}'
