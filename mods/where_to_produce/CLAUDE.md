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
спрашивает факт (`_pm<n> > 0`), а не `_plan_can_*`. Два прогона: 09-03 и 09-13.

**3 and 4 are separate and the traffic runs one way**: nothing the editor holds
is ever read by 3. **Before touching any `_plan_*`:
[`plan_gaps.md`](../../docs/investigations/plan_gaps.md).**

## Where it stands

**Его список — [`wtp_backlog.md`](../../docs/investigations/wtp_backlog.md), и он
открыт.** Построено всё, кроме 9.

**Без CM отмашка автостроя — две кнопки-виджета**
([`wtp_vanilla_autoexpand.md`](../../docs/investigations/wtp_vanilla_autoexpand.md)):
«первый ярус» начинает стройку и показывает точную цену движка,
«авторасширение» ставит галочку тому, что **строится**. Стоящее здание из нашего
окна недостижимо, и кнопка не горит. С CM всё как было. **Прогона не видело.**

**Принятое прогонами 09-14** — карты городских прав, окно замены, порядок
«Пригодности» — в
[`archive/wtp_brief_accepted_0914.md`](../../docs/archive/wtp_brief_accepted_0914.md).

**`_cov_pass` спрашивает локацию, считает покрытие только по сырью провинции и
берёт эпоху у позвавшего** — правила прохода целиком в
[`archive/wtp_brief_accepted_0914.md`](../../docs/archive/wtp_brief_accepted_0914.md).
**Прогона не видело.**

**Раздача, редактор, доливка, ряды, сводка** —
[`archive/wtp_brief_plan_rules.md`](../../docs/archive/wtp_brief_plan_rules.md),
[`archive/wtp_brief_rules.md`](../../docs/archive/wtp_brief_rules.md).

**Чужие окна** —
[`wtp_integration.md`](../../docs/investigations/wtp_integration.md): **`root` в
фильтре — не сам объект**; **мод ничего не делает периодически**.

**Подсказка игроку — одно предложение** («килотонны бесполезных объяснений»,
09-14); объяснение живёт в `generate.py`, не на экране.

**The build stamp is on «Техническая»**, before believing a fix failed. **Before
any `.gui`: [`pitfalls/windows.md`](../../docs/pitfalls/windows.md)** — every
rule in it this mod paid for, most twice.

**Not to be attempted again**: eight
([`archive/wtp_not_again.md`](../../docs/archive/wtp_not_again.md)). **Built by**
`generate.py`.
