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
from pathlib import Path

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
FITS = ("LessThanOrEqualTo_CFixedPoint(Add_CFixedPoint(IntToFixedPoint(PeaceOfferLateralView.GetTotalWarScoreCost), "
        "PeaceTreaty.GetWarScoreCost), PeaceOfferLateralView.GetWarScore)")


def at_step(i):
    return f"EqualTo_CFixedPoint({STEP}, {PV}('{var(i)}').GetValue)"


def gui():
    t = "\t" * 11
    helpers = []
    for i, _, _, _, _, _ in ITEMS:
        if i == "gold":
            continue
        cond = (f"And6({RUN}, {at_step(i)}, StringContains(PeaceTreaty.GetShortName, Localize('BAG_RTK_PT_MATCH_{i.upper()}')), "
                f"PeaceTreaty.IsEnabled, Not(PeaceTreaty.IsSelected), {FITS})")
        helpers.append(f"""{t}\t\t\t\t\t\twidget = {{
{t}\t\t\t\t\t\t\tsize = {{ 1 1 }}
{t}\t\t\t\t\t\t\tvisible_at_creation = no
{t}\t\t\t\t\t\t\tvisible = "[{cond}]"
{t}\t\t\t\t\t\t\tstate = {{
{t}\t\t\t\t\t\t\t\tname = _show
{t}\t\t\t\t\t\t\t\tduration = 0.05
{t}\t\t\t\t\t\t\t\ton_finish = "[PeaceTreaty.OnClick]"
{t}\t\t\t\t\t\t\t}}
{t}\t\t\t\t\t\t}}
""")
    gold = (f"And4({RUN}, {at_step('gold')}, PeaceOfferWarScoreTreatyGlue.IsIncWarScoreEnabled, "
            f"GreaterThan_CFixedPoint(PeaceOfferLateralView.GetWarScore, IntToFixedPoint(PeaceOfferLateralView.GetTotalWarScoreCost)))")
    return f"""{t}# BAG_RTK_PT_BEGIN — сгенерировано mods/rulers_toolkit/tools/gen_peace.py
{t}#bag_rtk: ШАБЛОН ДОГОВОРА (Помощник правителя). Сбросить договор и пройти
{t}# приоритеты 1..{MAX_STEP} со страницы CMF «Мир»: на каждом шаге берётся всё
{t}# своего приоритета, на что хватает очков.
{t}header_button_left = {{
{t}\tsize = {{30 30}}
{t}\tvisible = "[PeaceOfferLateralView.IsDemanding]"
{t}\tblockoverride "header_button_full_content" {{
{t}\t\ticon = {{
{t}\t\t\tsize = {{22 22 }}
{t}\t\t\ttexture = "gfx/interface/icons/peace_treaty/demand_peace.dds"
{t}\t\t}}
{t}\t}}
{t}\ttooltipwidget = {{
{t}\t\tBasicFunctionalTooltip = {{}}
{t}\t}}
{t}\taction_tooltip = {{
{t}\t\tclick_type = left
{t}\t\tclick_mode = single
{t}\t\ttitle = "BAG_RTK_PT_TT"
{t}\t\tdescription = "BAG_RTK_PT_DESC"
{t}\t\ton_action = "[PeaceOfferLateralView.OnResetPeaceOffer]"
{t}\t\ton_action = "[GetScriptedGui('bag_rtk_pt_start').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
{t}\t}}

{t}\t# Шагомер: пока идёт шаблон — каждые 0.4 с следующий приоритет.
{t}\twidget = {{
{t}\t\tsize = {{ 1 1 }}
{t}\t\tvisible_at_creation = no
{t}\t\tvisible = "[{RUN}]"
{t}\t\tstate = {{
{t}\t\t\tname = _show
{t}\t\t\tduration = 0.4
{t}\t\t\tnext = bag_rtk_pt_tick
{t}\t\t\ton_finish = "[GetScriptedGui('bag_rtk_pt_next').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
{t}\t\t}}
{t}\t\tstate = {{
{t}\t\t\tname = bag_rtk_pt_tick
{t}\t\t\tduration = 0.4
{t}\t\t\tnext = bag_rtk_pt_tick
{t}\t\t\ton_finish = "[GetScriptedGui('bag_rtk_pt_next').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
{t}\t\t}}
{t}\t}}

{t}\t# Золото: жать «+», пока на своём шаге и есть свободные очки.
{t}\twidget = {{
{t}\t\tsize = {{ 1 1 }}
{t}\t\tdatacontext = "[PeaceOfferLateralView.GetGoldTreaty]"
{t}\t\twidget = {{
{t}\t\t\tsize = {{ 1 1 }}
{t}\t\t\tvisible_at_creation = no
{t}\t\t\tvisible = "[{gold}]"
{t}\t\t\tstate = {{
{t}\t\t\t\tname = _show
{t}\t\t\t\tduration = 0.03
{t}\t\t\t\tnext = bag_rtk_pt_gold_more
{t}\t\t\t\ton_finish = "[PeaceOfferWarScoreTreatyGlue.OnIncLeftClick]"
{t}\t\t\t}}
{t}\t\t\tstate = {{
{t}\t\t\t\tname = bag_rtk_pt_gold_more
{t}\t\t\t\tduration = 0.03
{t}\t\t\t\tnext = bag_rtk_pt_gold_more
{t}\t\t\t\ton_finish = "[PeaceOfferWarScoreTreatyGlue.OnIncLeftClick]"
{t}\t\t\t}}
{t}\t\t}}
{t}\t}}

{t}\t# Пункты договора: по помощнику на пункт в каждой строке списка.
{t}\twidget = {{
{t}\t\tsize = {{ 1 1 }}
{t}\t\tvisible = "[{RUN}]"
{t}\t\tvbox = {{
{t}\t\t\tdatamodel = "[PeaceOfferLateralView.GetCategories]"
{t}\t\t\titem = {{
{t}\t\t\t\tvbox = {{
{t}\t\t\t\t\tdatamodel = "[PeaceOfferCategory.GetTreaties]"
{t}\t\t\t\t\titem = {{
{t}\t\t\t\t\t\twidget = {{
{t}\t\t\t\t\t\t\tsize = {{ 1 1 }}
""" + "".join(helpers) + f"""{t}\t\t\t\t\t\t}}
{t}\t\t\t\t\t}}
{t}\t\t\t\t}}
{t}\t\t\t}}
{t}\t\t}}
{t}\t}}
{t}}}
{t}# BAG_RTK_PT_END
"""


def loc(lang):
    ru = lang == "russian"
    lines = [BOM + f"l_{lang}:\n"]
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


def main():
    (MOD / "in_game/common/scripted_effects/bag_rtk_pt_generated.txt").write_text(effects(), encoding="utf-8", newline="\n")
    for lang in ("russian", "english"):
        (MOD / f"main_menu/localization/{lang}/bag_rtk_pt_l_{lang}.yml").write_text(loc(lang), encoding="utf-8", newline="\n")
    p = MOD / "in_game/gui/peace_offer_view.gui"
    s = p.read_text(encoding="utf-8-sig")
    t = "\t" * 11
    begin, end = f"{t}# BAG_RTK_PT_BEGIN", "# BAG_RTK_PT_END\n"
    if begin in s:
        a = s.index(begin)
        b = s.index(end, a) + len(end)
        s = s[:a] + gui() + s[b:]
    else:
        anchor = f"{t}#RESET OFFER\n"
        assert s.count(anchor) == 1
        s = s.replace(anchor, gui() + "\n" + anchor, 1)
    p.write_text(BOM + s, encoding="utf-8", newline="\n")
    print("peace template: generated")


if __name__ == "__main__":
    main()
