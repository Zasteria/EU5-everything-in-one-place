# `where_to_produce` — brief

## Four functions. Never mix them up.

«Ты постоянно смешиваешь функции плана и редактирования» — его слова.

**The mod page is three tabs and buttons that only open windows**, every setting
inside the window of its function; **anything technical belongs on
«Техническая»**
([`wtp_menu_rebuild.md`](../../docs/investigations/wtp_menu_rebuild.md)).

| # | what | where | files |
| --- | --- | --- | --- |
| 1 | **Choose the ground** | «Земля» on the mod page, or the map buttons in any window | `_zone_*`, `_region_*` |
| 2 | **One good or right → the best locations for it**, by what local RGOs pay | the ranking window: circles pick it, «Искать локации» runs it | `_score_*`, `_rank_*`, `_pick_*` |
| 3 | **A whole plan for that ground** — every production where it pays | the plan window: the caps and **three** switches there, «Пересчитать» runs it | `_plan_*` |
| 4 | **Editing that plan afterwards**, one building at a time | the editor window, and only there | `_edit_*` |

**Деревня — сущность, а не товар, и правило стоит в обоих местах** (09-12).

**Триггер живёт только в `common/scripted_triggers`** (ловит `check_script.py`).
**Ворота постановки после плана врут**: всё, что читается **после** раздачи,
спрашивает факт (`_pm<n> > 0`), а не `_plan_can_*`. Два прогона: 09-03 и 09-13.

**3 and 4 are separate and the traffic runs one way**: nothing the editor holds
is ever read by 3. **Before touching any `_plan_*`:
[`plan_gaps.md`](../../docs/investigations/plan_gaps.md).**

## Where it stands

**Его список — [`wtp_backlog.md`](../../docs/investigations/wtp_backlog.md), и он
открыт.** Построено всё, кроме 9. **Автострой закрыт его решением 2026-09-14** —
не предлагать: `Building` создаёт только движок
([`RESEARCH.md`](../../docs/RESEARCH.md)).

**Карты городских прав CM dev перенесены целиком** (`_trmm_*`), и выгода земли
под грамоту `_rq<k>` считается его методом —
[`wtp_town_right_map.md`](../../docs/investigations/wtp_town_right_map.md).

**Окно замены принято прогоном 09-14** целиком, «−» на `mason` тоже.

**`_cov_pass` был пересказом `_trmm_cov_*`, а не его вызовом, и оттого врал**
(09-14): пересказ потерял вычитание уже выданной грамоты и размазал усреднение
своего РГО с `dyes`/`wine` на все двадцать товаров. Теперь `_covl_<товар>` =
`_trmm_lm_<товар>` его значением; **отличие от карты осталось одно — лучший
способ из доступных**. Подсказка «Пригодности» тоже наша: лесенка `_rqr<k>` плюс
«итог = сырьё + модификатор». **Прогона не видело.**

**Раздача, редактор, доливка, ряды, сводка** —
[`archive/wtp_brief_plan_rules.md`](../../docs/archive/wtp_brief_plan_rules.md),
[`archive/wtp_brief_rules.md`](../../docs/archive/wtp_brief_rules.md).

**Чужие окна** —
[`wtp_integration.md`](../../docs/investigations/wtp_integration.md): **`root` в
фильтре — не сам объект**; **мод ничего не делает периодически**. **Список CMF
без своего `_on_changed` не рисуется, а группа рисуется** (ловит чекер).

**Подсказка игроку — одно предложение** («килотонны бесполезных объяснений»,
09-14); объяснение живёт в `generate.py`, не на экране.

**The build stamp is on «Техническая»**, before believing a fix failed. **Before
any `.gui`: [`pitfalls/windows.md`](../../docs/pitfalls/windows.md)** — every
rule in it this mod paid for, most twice.

**Not to be attempted again**: eight
([`archive/wtp_not_again.md`](../../docs/archive/wtp_not_again.md)). **Built by**
`generate.py`.
