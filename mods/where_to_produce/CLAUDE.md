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

**Ворота постановки после плана врут**: всё, что читается **после** раздачи,
спрашивает факт (`_pm<n> > 0`), а не `_plan_can_*` (09-03, 09-13). **3 и 4
разделены, движение одностороннее.** **Before any `_plan_*`:
[`plan_gaps.md`](../../docs/investigations/plan_gaps.md).**

## Where it stands

**Его список — [`wtp_backlog.md`](../../docs/investigations/wtp_backlog.md), и он
открыт.** Построено всё, кроме 9. **Автострой закрыт его решением 2026-09-14** —
не предлагать: `Building` создаёт только движок
([`RESEARCH.md`](../../docs/RESEARCH.md)).

**Карты городских прав CM dev перенесены целиком** (`_trmm_*`), выгода земли под
грамоту `_rq<k>` — его метод, там же четыре правила `_cov_pass`:
[`wtp_town_right_map.md`](../../docs/investigations/wtp_town_right_map.md).

**Счёт обязан спрашивать локацию** (`_cov_pass` → `_stands_<здание>`), **а сам
`_stands_` под галочкой ранга — сторону**: иначе `market_village` вставал в
городе (09-14, [`pitfalls/script.md`](../../docs/pitfalls/script.md)).

**Раздачу грамот не правят на глаз** — три правки 09-14 ушли впустую:
`tools/rights_sim.py <дамп>` гоняет её на его числах, `--ceilings` даёт потолки.
**У специализации раздача своя, и лестницы в ней нет нарочно**: «лучшее ставить,
и в ней вполне может быть 0 каких-то прав». В обычном плане отставание —
**уклон** (`_rlagw<k>`), в **городах**; галочка «Грамоты — поровну» (снята,
взаимоисключима со специализацией) даёт разброс 3..6 — **принято 09-14**.
**Грамота ставится руками**, **«+1»/«−1» ходят провинцией**. Разбор —
[`wtp_backlog.md`](../../docs/investigations/wtp_backlog.md).

**Раздача, редактор, доливка, ряды, сводка** —
[`archive/wtp_brief_plan_rules.md`](../../docs/archive/wtp_brief_plan_rules.md),
[`archive/wtp_brief_rules.md`](../../docs/archive/wtp_brief_rules.md).

**Чужие окна** —
[`wtp_integration.md`](../../docs/investigations/wtp_integration.md): **`root` в
фильтре — не сам объект**; **мод ничего не делает периодически**.

**Подсказка игроку — одно предложение**, объяснение живёт в `generate.py`.

**The build stamp is on «Техническая»**, before believing a fix failed. **Before
any `.gui`: [`pitfalls/windows.md`](../../docs/pitfalls/windows.md)** — every
rule in it this mod paid for, most twice.

**Not to be attempted again**: eight
([`archive/wtp_not_again.md`](../../docs/archive/wtp_not_again.md)). **Built by**
`generate.py`.
