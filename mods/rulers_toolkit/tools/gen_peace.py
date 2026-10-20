"""Шаблон мирного договора: генератор (rulers_toolkit, его просьба 10-20).

Пишет из списка ITEMS ниже:
  in_game/common/scripted_effects/bag_rtk_pt_generated.txt — страница CMF «Мир»
      (по ползунку приоритета на пункт) и обратный звонок;
  кусок `peace_offer_view.gui` между метками BAG_RTK_PT_BEGIN / BAG_RTK_PT_END —
      кнопка шаблона, шагомер и по помощнику на каждый пункт договора;
  main_menu/localization/{russian,english}/bag_rtk_pt_l_*.yml.

Пункт договора окно мира отдаёт только названием (`PeaceTreaty.GetShortName`,
зонд 10-20, его скрин): тип не узнать, поэтому пункт узнаётся по куску текста
названия на языке игры (`StringContains`). Золото — отдельный «+»
(`PeaceOfferLateralView.GetGoldTreaty`).

    python3 mods/rulers_toolkit/tools/gen_peace.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
import quiet_logs  # noqa: E402  строки журнала — под галочкой «Журнал»

MOD = Path(__file__).resolve().parent.parent

# id, по-русски, по-английски (имя в CMF), кусок названия ru / en, приоритет по умолчанию.
# Приоритет 0 — пункт выключен. Шаги идут от 1 до MAX_STEP.
ITEMS = [
    ("rep", "Контрибуции", "War reparations", "контрибуци", "eparations", 1),
    ("gold", "Золото", "Gold", None, None, 2),
    ("annul", "Расторжение договоров", "Annul treaties", "расторгают все", "nnul", 3),
    ("access", "Право прохода войск", "Military access", "проход войск", "ilitary access", 3),
    ("food", "Доступ к продовольствию", "Food access", "продовольств", "ood access", 3),
    ("piracy", "Борьба с пиратством", "Anti-piracy", "пиратств", "iracy", 3),
    ("build", "Запрет строительства", "Building ban", "вести строительство", "uild", 3),
    ("slaves", "Освобождение рабов", "Free the slaves", "рабов", "slaves", 3),
    ("hum", "Унижение", "Humiliation", "Унижение", "umiliat", 4),
]
MAX_STEP = 9

BOM = "﻿"


def var(i):
    return f"bag_rtk_pt_p_{i}"


def effects():
    out = [BOM + "# Сгенерировано tools/gen_peace.py — не править руками.\n",
           "# Страница CMF «Мир»: по ползунку приоритета на пункт договора. Scope: country.\n",
           "bag_rtk_pt_register = {\n"]
    for i, ru, en, _, _, d in ITEMS:
        out.append(f"""\tcmm_register_slider_setting = {{
\t\tmod_id = bag_rtk
\t\tsetting_id = pt_{i}
\t\ttab_id = peace
\t\tgroup_id = template
\t\tdefault_value = {d}
\t\tmin_value = 0
\t\tmax_value = {MAX_STEP}
\t\tstep_value = 1
\t}}
\tcmm_sync_setting_alias = {{
\t\tsetting = bag_rtk__pt_{i}
\t\talias = {var(i)}
\t}}
""")
    out.append("}\n\n# Обратный звонок CMF. Scope: country.\nbag_rtk_pt_callback = {\n\tswitch = {\n\t\ttrigger = var:cmf_callback\n")
    for i, *_ in ITEMS:
        out.append(f"""\t\tflag:bag_rtk__pt_{i} = {{
\t\t\tcmm_sync_setting_alias = {{
\t\t\t\tsetting = bag_rtk__pt_{i}
\t\t\t\talias = {var(i)}
\t\t\t}}
\t\t}}
""")
    out.append("\t}\n}\n")
    return "".join(out)


PV = "GetPlayer.MakeScope.GetVariable"
STEP = f"{PV}('bag_rtk_pt_step').GetValue"
RUN = f"{PV}('bag_rtk_pt_run').IsSet"
LOG = f"{PV}('bag_rtk_log_on').IsSet"


def _yn(cond: str) -> str:
    return "[Select_CString(" + cond + ", 'Y', 'n')]"


def debug_loc() -> str:
    head = (" BAG_RTK_PT_DBG: \"PT run=" + _yn(RUN)
            + " step=[GetPlayer.MakeScope.GetVariable('bag_rtk_pt_step').GetValue|0] "
            + " ".join(i + "=[GetPlayer.MakeScope.GetVariable('" + var(i) + "').GetValue|0]" for i, *_ in ITEMS)
            + " ws=[PeaceOfferLateralView.GetWarScore|0] cost=[PeaceOfferLateralView.GetTotalWarScoreCost]\"\n")
    row = (" BAG_RTK_PT_DBG_ROW: \"  "
           + " ".join(i + "=" + _yn("StringContains(PeaceTreaty.GetShortName, Localize('BAG_RTK_PT_MATCH_" + i.upper() + "'))")
                      for i, _, _, mr, _, _ in ITEMS if mr)
           + " en=" + _yn("PeaceTreaty.IsEnabled") + " sel=" + _yn("PeaceTreaty.IsSelected")
           + " fits=" + _yn(FITS) + " [PeaceTreaty.GetWarScoreCost|1]\"\n")
    return head + row
FITS = ("LessThanOrEqualTo_CFixedPoint(Add_CFixedPoint(IntToFixedPoint(PeaceOfferLateralView.GetTotalWarScoreCost), "
        "PeaceTreaty.GetWarScoreCost), PeaceOfferLateralView.GetWarScore)")


def at_step(i):
    return f"EqualTo_CFixedPoint({STEP}, {PV}('{var(i)}').GetValue)"


REP_BUTTON = """									#bag_rtk: ДИПРЕПУТАЦИЯ НА ВРЕМЯ МИРА (Помощник правителя)
									header_button_left = {
										size = {30 30}
										blockoverride "header_button_full_content" {
											icon = {
												size = {22 22 }
												texture = "gfx/interface/icons/flat_icons/diplomatic_reputation.dds"
												alpha = "[Select_float(GetPlayer.MakeScope.GetVariable('bag_rtk_rep_on').IsSet, '(float)1', '(float)0.45')]"
											}
										}
										tooltipwidget = {
											BasicFunctionalTooltip = {}
										}
										action_tooltip = {
											click_type = left
											click_mode = single
											title = "[Select_CString(GetPlayer.MakeScope.GetVariable('bag_rtk_rep_on').IsSet, Localize('BAG_RTK_REP_OFF_TT'), Localize('BAG_RTK_REP_ON_TT'))]"
											description = "BAG_RTK_REP_DESC"
											on_action = "[GetScriptedGui('bag_rtk_rep_toggle').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
										}
									}
"""


def button():
    """Our two buttons in a row of their own above the summary row: in the summary
    row they pushed the war-score cost out of the window (his screenshot 10-20)."""
    t = "\t" * 7
    return f"""{t}# BAG_RTK_PT_BUTTON_BEGIN — сгенерировано mods/rulers_toolkit/tools/gen_peace.py
{t}hbox = {{
{t}\tlayoutpolicy_horizontal = expanding
{t}\tmargin = {{ 5 0 }}
{t}\tspacing = 5
{t}\texpand = {{}}
{REP_BUTTON}
{t}\t#bag_rtk: ШАБЛОН ДОГОВОРА (Помощник правителя): сбросить договор и запустить
{t}\t# шагомер (сам он — в начале панели, BAG_RTK_PT_DRIVER).
{t}\theader_button_left = {{
{t}\t\tsize = {{30 30}}
{t}\t\tvisible = "[PeaceOfferLateralView.IsDemanding]"
{t}\t\tblockoverride "header_button_full_content" {{
{t}\t\t\ticon = {{
{t}\t\t\t\tsize = {{22 22 }}
{t}\t\t\t\ttexture = "gfx/interface/icons/peace_treaty/demand_peace.dds"
{t}\t\t\t}}
{t}\t\t}}
{t}\t\ttooltipwidget = {{
{t}\t\t\tBasicFunctionalTooltip = {{}}
{t}\t\t}}
{t}\t\taction_tooltip = {{
{t}\t\t\tclick_type = left
{t}\t\t\tclick_mode = single
{t}\t\t\ttitle = "BAG_RTK_PT_TT"
{t}\t\t\tdescription = "BAG_RTK_PT_DESC"
{t}\t\t\ton_action = "[PeaceOfferLateralView.OnResetPeaceOffer]"
{t}\t\t\ton_action = "[GetScriptedGui('bag_rtk_pt_start').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
{t}\t\t}}
{t}\t}}
{t}}}
{t}# BAG_RTK_PT_BUTTON_END
"""


def driver():
    t = "	" * 3
    helpers = []
    for i, _, _, _, _, _ in ITEMS:
        if i == "gold":
            continue
        cond = (f"And6({RUN}, {at_step(i)}, StringContains(PeaceTreaty.GetShortName, Localize('BAG_RTK_PT_MATCH_{i.upper()}')), "
                f"PeaceTreaty.IsEnabled, Not(PeaceTreaty.IsSelected), {FITS})")
        helpers.append(f"""{t}						widget = {{
{t}							size = {{ 1 1 }}
{t}							visible_at_creation = no
{t}							visible = "[{cond}]"
{t}							state = {{
{t}								name = _show
{t}								duration = 0.05
{t}								on_finish = "[PeaceTreaty.OnClick]"
{t}								on_finish = "[GetScriptedGui('bag_rtk_pt_clicked').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
{t}							}}
{t}						}}
""")
    # With the log tick on, each treaty row says what the helpers see (10-20: the
    # template stepped and clicked nothing, and debug_log cannot read GUI values).
    helpers.append(f"""{t}						text_single = {{
{t}							visible = "[{LOG}]"
{t}							fontsize = 11
{t}							text = "BAG_RTK_PT_DBG_ROW"
{t}						}}
""")
    gold = (f"And4({RUN}, {at_step('gold')}, PeaceOfferWarScoreTreatyGlue.IsIncWarScoreEnabled, "
            f"GreaterThan_CFixedPoint(PeaceOfferLateralView.GetWarScore, IntToFixedPoint(PeaceOfferLateralView.GetTotalWarScoreCost)))")
    return f"""{t}# BAG_RTK_PT_DRIVER_BEGIN — сгенерировано mods/rulers_toolkit/tools/gen_peace.py
{t}# Шаблон договора: шагомер и помощники. Невидимые, нулевого размера; живут здесь,
{t}# а не в кнопке — в 0.9.1 внутри кнопки они не срабатывали.
{t}widget = {{
{t}	size = {{ 0 0 }}

{t}	text_single = {{
{t}		visible = "[{LOG}]"
{t}		position = {{ 0 -18 }}
{t}		fontsize = 11
{t}		text = "BAG_RTK_PT_DBG"
{t}	}}

{t}	# Шагомер: пока идёт шаблон — каждые 0.4 с следующий приоритет.
{t}	widget = {{
{t}		size = {{ 1 1 }}
{t}		visible_at_creation = no
{t}		visible = "[{RUN}]"
{t}		state = {{
{t}			name = _show
{t}			duration = 0.4
{t}			next = bag_rtk_pt_tick
{t}			on_finish = "[GetScriptedGui('bag_rtk_pt_next').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
{t}		}}
{t}		state = {{
{t}			name = bag_rtk_pt_tick
{t}			duration = 0.4
{t}			next = bag_rtk_pt_tick
{t}			on_finish = "[GetScriptedGui('bag_rtk_pt_next').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
{t}		}}
{t}	}}

{t}	# Золото: жать «+», пока на своём шаге и есть свободные очки.
{t}	widget = {{
{t}		size = {{ 1 1 }}
{t}		datacontext = "[PeaceOfferLateralView.GetGoldTreaty]"
{t}		widget = {{
{t}			size = {{ 1 1 }}
{t}			visible_at_creation = no
{t}			visible = "[{gold}]"
{t}			state = {{
{t}				name = _show
{t}				duration = 0.03
{t}				next = bag_rtk_pt_gold_more
{t}				on_finish = "[PeaceOfferWarScoreTreatyGlue.OnIncLeftClick]"
{t}			}}
{t}			state = {{
{t}				name = bag_rtk_pt_gold_more
{t}				duration = 0.03
{t}				next = bag_rtk_pt_gold_more
{t}				on_finish = "[PeaceOfferWarScoreTreatyGlue.OnIncLeftClick]"
{t}			}}
{t}		}}
{t}	}}

{t}	# Пункты договора: по помощнику на пункт в каждой строке списка.
{t}	widget = {{
{t}		size = {{ 1 1 }}
{t}		vbox = {{
{t}			datamodel = "[PeaceOfferLateralView.GetCategories]"
{t}			item = {{
{t}				vbox = {{
{t}					datamodel = "[PeaceOfferCategory.GetTreaties]"
{t}					item = {{
{t}						widget = {{
{t}							size = {{ 1 1 }}
""" + "".join(helpers) + f"""{t}						}}
{t}					}}
{t}				}}
{t}			}}
{t}		}}
{t}	}}
{t}}}
{t}# BAG_RTK_PT_DRIVER_END
"""


def loc(lang):
    ru = lang == "russian"
    lines = [BOM + f"l_{lang}:\n"]
    lines.append(debug_loc())
    lines.append(' bag_rtk__peace_name: "%s"\n' % ("Мир" if ru else "Peace"))
    lines.append(' bag_rtk__peace__template_name: "%s"\n' % ("Шаблон мирного договора: приоритеты" if ru else "Peace template: priorities"))
    for i, rn, en, mr, me, _ in ITEMS:
        lines.append(f' bag_rtk__pt_{i}_name: "{rn if ru else en}"\n')
        lines.append(' bag_rtk__pt_%s_desc: "%s"\n' % (i, "Шаг, на котором кнопка шаблона берёт этот пункт: 1 — первым. 0 — не брать." if ru
                                                       else "Step at which the template button takes this term: 1 goes first. 0 means never."))
        if mr:
            lines.append(f' BAG_RTK_PT_MATCH_{i.upper()}: "{mr if ru else me}"\n')
    if ru:
        lines.append(' BAG_RTK_PT_TT: "Шаблон договора"\n')
        lines.append(' BAG_RTK_PT_DESC: "Помощник правителя. Сбрасывает договор и набирает его по приоритетам со страницы CMF «Помощник правителя» → «Мир»: сначала всё с приоритетом 1, потом 2 и так далее, пока хватает очков войны. Золото берётся «+» до упора."\n')
    else:
        lines.append(' BAG_RTK_PT_TT: "Peace template"\n')
        lines.append(' BAG_RTK_PT_DESC: "Ruler\'s Toolkit. Clears the offer and fills it by the priorities on the CMF page Ruler\'s Toolkit, Peace: everything at priority 1 first, then 2 and so on while war score lasts. Gold is raised with + as far as it goes."\n')
    return "".join(lines)


def splice(s, begin, end, text, anchor, before):
    if begin in s:
        a = s.rindex("\n", 0, s.index(begin)) + 1
        b = s.index("\n", s.index(end, a)) + 1
        return s[:a] + text + s[b:]
    assert s.count(anchor) == 1, anchor
    return s.replace(anchor, text + "\n" + anchor, 1) if before else s.replace(anchor, anchor + text, 1)


def start_effect():
    """Недостающие приоритеты (сейв старше вкладки «Мир») — по умолчанию."""
    out = []
    for i, *_, d in ITEMS:
        out.append(f"\tif = {{\n\t\tlimit = {{ NOT = {{ has_variable = {var(i)} }} }}\n"
                   f"\t\tset_variable = {{ name = {var(i)} value = {d} }}\n"
                   f"\t\tdebug_log = \"bag_rtk: peace template, {i} priority missing, default {d}\"\n\t}}\n")
    return "# Сгенерировано tools/gen_peace.py. Scope: country.\nbag_rtk_pt_defaults = {\n" + "".join(out) + "}\n"


def main():
    (MOD / "in_game/common/scripted_effects/bag_rtk_pt_generated.txt").write_text(
        quiet_logs.quiet(effects() + "\n" + start_effect(), "bag_rtk_log"), encoding="utf-8", newline="\n")
    for lang in ("russian", "english"):
        (MOD / f"main_menu/localization/{lang}/bag_rtk_pt_l_{lang}.yml").write_text(loc(lang), encoding="utf-8", newline="\n")
    p = MOD / "in_game/gui/peace_offer_view.gui"
    s = p.read_text(encoding="utf-8-sig")
    reset = "\t" * 11 + "#RESET OFFER\n"
    # 0.9.1 держал весь кусок у кнопки — убрать.
    if "# BAG_RTK_PT_BEGIN" in s:
        a = s.rindex("\n", 0, s.index("# BAG_RTK_PT_BEGIN")) + 1
        b = s.index("\n", s.index("# BAG_RTK_PT_END")) + 1
        s = s[:a] + s[b:]
        s = s.replace("\n\n" + reset, "\n" + reset, 1)
    s = splice(s, "# BAG_RTK_PT_BUTTON_BEGIN", "# BAG_RTK_PT_BUTTON_END", button(),
               "\t" * 7 + "#SUM UP OF PEACE CONSECUENCES\n", True)
    panel = ("\tblockoverride \"panel_content\" {\n\t\tvbox = {\n\t\t\tusing = layoutpolicy_expanding\n"
             "\t\t\tusing = bg_main_inner_alt\n\t\t\tusing = window_main_tabs_margin_alt\n")
    s = splice(s, "# BAG_RTK_PT_DRIVER_BEGIN", "# BAG_RTK_PT_DRIVER_END", driver(), panel, False)
    p.write_text(BOM + s, encoding="utf-8", newline="\n")
    print("peace template: generated")


if __name__ == "__main__":
    main()
