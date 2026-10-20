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
    cat = (" BAG_RTK_PT_DBG_CAT: \"# [PeaceOfferCategory.GetName] exp=" + _yn("PeaceOfferCategory.IsExpanded")
           + " poss=" + _yn("PeaceOfferCategory.HasPossibleTreaties") + "\"\n")
    return head + row + cat
# In whole points: `IntToFixedPoint` returns a float despite its name, and every
# comparison built on it failed silently (10-20 log: FetchData failed, 108 768
# times), so no helper and no gold ever fired.
FITS = ("LessThanOrEqualTo_int32(Add_int32(PeaceOfferLateralView.GetTotalWarScoreCost, "
        "FixedPointToInt(PeaceTreaty.GetWarScoreCost)), FixedPointToInt(PeaceOfferLateralView.GetWarScore))")


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


# Которая категория окна держит пункт (его скрины 10-20: категории — гармошка,
# пункты отдаёт только раскрытая). Шаблон раскрывает их по очереди: на каждом
# приоритете фаза 1 — «Другие договоры», фаза 2 — «Договоры о державах».
CATEGORY = {"rep": "MISC_CATEGORY", "annul": "MISC_CATEGORY", "access": "MISC_CATEGORY",
            "food": "MISC_CATEGORY", "piracy": "MISC_CATEGORY", "slaves": "MISC_CATEGORY",
            "build": "COUNTRY_CATEGORY", "hum": "COUNTRY_CATEGORY"}
PHASES = ("MISC_CATEGORY", "COUNTRY_CATEGORY")
SUB = f"{PV}('bag_rtk_pt_sub').GetValue"


def current_category() -> str:
    parts = [f"And(EqualTo_CFixedPoint({SUB}, '(CFixedPoint){n}'), "
             f"EqualTo_string(PeaceOfferCategory.GetName, Localize('{key}')))"
             for n, key in enumerate(PHASES, 1)]
    return "Or(" + ", ".join(parts) + ")"


def driver():
    t = "\t" * 3
    T = "\t"
    helpers = []
    for i, _, _, mr, _, _ in ITEMS:
        if not mr:
            continue
        cond = (f"And6({RUN}, {at_step(i)}, StringContains(PeaceTreaty.GetShortName, Localize('BAG_RTK_PT_MATCH_{i.upper()}')), "
                f"PeaceTreaty.IsEnabled, Not(PeaceTreaty.IsSelected), {FITS})")
        helpers.append(
            f"{t}{T*6}widget = {{\n"
            f"{t}{T*7}size = {{ 1 1 }}\n"
            f"{t}{T*7}visible_at_creation = no\n"
            f"{t}{T*7}visible = \"[{cond}]\"\n"
            f"{t}{T*7}state = {{\n"
            f"{t}{T*8}name = _show\n"
            f"{t}{T*8}duration = 0.05\n"
            f"{t}{T*8}on_finish = \"[PeaceTreaty.OnClick]\"\n"
            f"{t}{T*8}on_finish = \"[GetScriptedGui('bag_rtk_pt_clicked').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]\"\n"
            f"{t}{T*7}}}\n"
            f"{t}{T*6}}}\n")
    helpers.append(
        f"{t}{T*6}text_single = {{\n"
        f"{t}{T*7}visible = \"[{LOG}]\"\n"
        f"{t}{T*7}fontsize = 11\n"
        f"{t}{T*7}text = \"BAG_RTK_PT_DBG_ROW\"\n"
        f"{t}{T*6}}}\n")
    gold = (f"And5({RUN}, {at_step('gold')}, EqualTo_CFixedPoint({SUB}, '(CFixedPoint)1'), "
            f"PeaceOfferWarScoreTreatyGlue.IsIncWarScoreEnabled, "
            f"GreaterThan_int32(FixedPointToInt(PeaceOfferLateralView.GetWarScore), PeaceOfferLateralView.GetTotalWarScoreCost))")
    tick = "[GetScriptedGui('bag_rtk_pt_next').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
    out = [
        f"{t}# BAG_RTK_PT_DRIVER_BEGIN — сгенерировано mods/rulers_toolkit/tools/gen_peace.py\n",
        f"{t}# Шаблон договора: шагомер (приоритет × категория), раскрытие категорий и\n",
        f"{t}# помощники у пунктов. Невидимое места в окне не берёт.\n",
        f"{t}widget = {{\n",
        f"{t}{T}size = {{ 0 0 }}\n",
        f"{t}{T}text_single = {{\n{t}{T*2}visible = \"[{LOG}]\"\n{t}{T*2}position = {{ 0 -18 }}\n",
        f"{t}{T*2}fontsize = 11\n{t}{T*2}text = \"BAG_RTK_PT_DBG\"\n{t}{T}}}\n",
        f"{t}{T}# Шагомер: каждые 0.35 с следующая фаза (категория), потом приоритет.\n",
        f"{t}{T}widget = {{\n{t}{T*2}size = {{ 1 1 }}\n{t}{T*2}visible_at_creation = no\n{t}{T*2}visible = \"[{RUN}]\"\n",
        f"{t}{T*2}state = {{\n{t}{T*3}name = _show\n{t}{T*3}duration = 0.35\n{t}{T*3}next = bag_rtk_pt_tick\n{t}{T*3}on_finish = \"{tick}\"\n{t}{T*2}}}\n",
        f"{t}{T*2}state = {{\n{t}{T*3}name = bag_rtk_pt_tick\n{t}{T*3}duration = 0.35\n{t}{T*3}next = bag_rtk_pt_tick\n{t}{T*3}on_finish = \"{tick}\"\n{t}{T*2}}}\n",
        f"{t}{T}}}\n",
        f"{t}{T}# Золото: жать «+», пока на своём шаге и есть свободные очки.\n",
        f"{t}{T}widget = {{\n{t}{T*2}size = {{ 1 1 }}\n{t}{T*2}datacontext = \"[PeaceOfferLateralView.GetGoldTreaty]\"\n",
        f"{t}{T*2}widget = {{\n{t}{T*3}size = {{ 1 1 }}\n{t}{T*3}visible_at_creation = no\n{t}{T*3}visible = \"[{gold}]\"\n",
        f"{t}{T*3}state = {{\n{t}{T*4}name = _show\n{t}{T*4}duration = 0.03\n{t}{T*4}next = bag_rtk_pt_gold_more\n",
        f"{t}{T*4}on_finish = \"[PeaceOfferWarScoreTreatyGlue.OnIncLeftClick]\"\n{t}{T*3}}}\n",
        f"{t}{T*3}state = {{\n{t}{T*4}name = bag_rtk_pt_gold_more\n{t}{T*4}duration = 0.03\n{t}{T*4}next = bag_rtk_pt_gold_more\n",
        f"{t}{T*4}on_finish = \"[PeaceOfferWarScoreTreatyGlue.OnIncLeftClick]\"\n{t}{T*3}}}\n",
        f"{t}{T*2}}}\n{t}{T}}}\n",
        f"{t}}}\n\n",
        f"{t}# Категории — гармошка: пункты отдаёт только раскрытая. Своя фаза раскрывает\n",
        f"{t}# свою категорию; помощники у пунктов жмут то, что на этом приоритете.\n",
        f"{t}vbox = {{\n{t}{T}layoutpolicy_horizontal = expanding\n{t}{T}ignoreinvisible = yes\n",
        f"{t}{T}datamodel = \"[PeaceOfferLateralView.GetCategories]\"\n",
        f"{t}{T}item = {{\n{t}{T*2}vbox = {{\n{t}{T*3}layoutpolicy_horizontal = expanding\n{t}{T*3}ignoreinvisible = yes\n",
        f"{t}{T*3}widget = {{\n{t}{T*4}size = {{ 1 1 }}\n{t}{T*4}visible_at_creation = no\n",
        f"{t}{T*4}visible = \"[And4({RUN}, {current_category()}, Not(PeaceOfferCategory.IsExpanded), PeaceOfferCategory.HasPossibleTreaties)]\"\n",
        f"{t}{T*4}state = {{\n{t}{T*5}name = _show\n{t}{T*5}duration = 0.03\n{t}{T*5}on_finish = \"[PeaceOfferCategory.Expand]\"\n{t}{T*4}}}\n",
        f"{t}{T*3}}}\n",
        f"{t}{T*3}text_single = {{\n{t}{T*4}visible = \"[{LOG}]\"\n{t}{T*4}fontsize = 11\n{t}{T*4}text = \"BAG_RTK_PT_DBG_CAT\"\n{t}{T*3}}}\n",
        f"{t}{T*3}vbox = {{\n{t}{T*4}layoutpolicy_horizontal = expanding\n{t}{T*4}ignoreinvisible = yes\n",
        f"{t}{T*4}datamodel = \"[PeaceOfferCategory.GetTreaties]\"\n",
        f"{t}{T*4}item = {{\n{t}{T*5}vbox = {{\n{t}{T*6}layoutpolicy_horizontal = expanding\n{t}{T*6}ignoreinvisible = yes\n",
        "".join(helpers),
        f"{t}{T*5}}}\n{t}{T*4}}}\n{t}{T*3}}}\n{t}{T*2}}}\n{t}{T}}}\n{t}}}\n",
        f"{t}# BAG_RTK_PT_DRIVER_END\n",
    ]
    return "".join(out)


def stepper_guis() -> str:
    """bag_rtk_pt_start / bag_rtk_pt_next: priority by priority, each in two phases."""
    top = "\n".join(f"\t\tif = {{ limit = {{ var:{var(i)} > var:bag_rtk_pt_max }} set_variable = {{ name = bag_rtk_pt_max value = var:{var(i)} }} }}"
                    for i, *_ in ITEMS)
    return f"""
# Шаблон договора (`tools/gen_peace.py`): кнопка запускает шагомер. Приоритет
# идёт до самого большого из выставленных; на каждом — две фазы (категории).
# Scope: country.
bag_rtk_pt_start = {{
\tscope = country
\tis_shown = {{ always = yes }}
\tis_valid = {{ always = yes }}
\teffect = {{
\t\tbag_rtk_pt_defaults = yes
\t\tset_variable = {{ name = bag_rtk_pt_max value = 0 }}
{top}
\t\tset_variable = {{ name = bag_rtk_pt_step value = 0 }}
\t\tset_variable = {{ name = bag_rtk_pt_sub value = {len(PHASES)} }}
\t\tset_variable = {{ name = bag_rtk_pt_run value = yes }}
\t\tdebug_log = "bag_rtk: peace template started"
\t}}
}}

# Следующая фаза; после последней — следующий приоритет; после самого
# большого — стоп. Scope: country.
bag_rtk_pt_next = {{
\tscope = country
\tis_shown = {{ always = yes }}
\tis_valid = {{ always = yes }}
\teffect = {{
\t\tif = {{
\t\t\tlimit = {{ var:bag_rtk_pt_sub < {len(PHASES)} }}
\t\t\tchange_variable = {{ name = bag_rtk_pt_sub add = 1 }}
\t\t}}
\t\telse = {{
\t\t\tset_variable = {{ name = bag_rtk_pt_sub value = 1 }}
\t\t\tchange_variable = {{ name = bag_rtk_pt_step add = 1 }}
\t\t}}
\t\tif = {{
\t\t\tlimit = {{ var:bag_rtk_pt_step > var:bag_rtk_pt_max }}
\t\t\tremove_variable = bag_rtk_pt_run
\t\t\tdebug_log = "bag_rtk: peace template done"
\t\t}}
\t}}
}}

# Помощник шаблона нажал пункт (зонд). Scope: country.
bag_rtk_pt_clicked = {{
\tscope = country
\tis_shown = {{ always = yes }}
\tis_valid = {{ always = yes }}
\teffect = {{
\t\tdebug_log = "bag_rtk: peace template, a term clicked"
\t}}
}}
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
    (MOD / "in_game/common/scripted_guis/bag_rtk_pt_scripted_gui.txt").write_text(
        BOM + "# Сгенерировано tools/gen_peace.py — не править руками.\n"
        + quiet_logs.quiet(stepper_guis(), "bag_rtk_log"), encoding="utf-8", newline="\n")
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
