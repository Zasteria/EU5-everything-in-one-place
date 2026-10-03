# `where_to_produce`: правила редактора и раздачи, выписанные из брифа

**Живой бриф — [`mods/where_to_produce/CLAUDE.md`](../../../mods/where_to_produce/CLAUDE.md).**
Здесь то, что он больше не вмещает: правила, которые не меняются и которые
достаточно найти через `tools/kb.py`, когда сессия трогает именно их.

## Редактор

**A preference is an edit, not a term in the objective**: `bag_wtp_edit_*` moves
one building a press, **the round trip is no undo**, and **a pin is a star**
(`_lock<n>`). **A charter is not a building**: every town holds exactly one, so
«+1»/«−1» *moves* it, bundle and all. **The changes window is a diff, not a
chronology**, shelved at his word; the journal is `WTP PRESS`. **«Расширить» доливает новую землю**: новое = выбранное минус
`_plan_touched`, старое заморожено, **оно сужает `_candidates`**. **Земля
редактора своя** (`_sel_keep_plan`). **Ряд плана рисует товар над домиком двумя
датамоделями**, `WTP ROWPAIR` ловит расхождение.
**Равномерность держит уровень, а не квота**: круг поднимает `_plan_lvl` на
единицу, товар берёт не больше одного домика за круг, и **полоса выгоды решает
«где», а не «сколько»**. Покрытие — это круг 1, открытая лестница — сухой круг.
`_pq`/`_pqt`/`_pqr` остались потолками: общий и по сторонам, чтобы один товар не
выгреб дефицитную сторону. **Весов город/село нет и не будет**, и **выхлоп
сторону не различает** — обе версии отвергнуты числами.
**`_edit_set_quota` этого ещё не знает.** **Ступень дефицита — доля земли**
(2…32 %), а старые 1/2/4/8/16 — пол. **Выхлоп отвергнут владельцем**; `_pout<n>` остался зондом
([`plan_share_sides.md`](plan_share_sides.md),
[`plan_as_reservation.md`](plan_as_reservation.md)).
**Второй режим плана — «Специализация»**, кнопка на странице мода: провинция
отдаёт лучшую грамоту всем своим городам, свободная ячейка — тому, кто платит в
ней больше всех, и никаких долей
([`plan_specialisation.md`](plan_specialisation.md)).
**Сводка по товарам** — иконка в окне плана: строка на товар и причина, на чём он
остановился; считается на открытие, по `_plan_touched`.
[`wtp_editor_design.md`](wtp_editor_design.md).

## Где что живёт

Устройство редактора — [`wtp_editor_design.md`](wtp_editor_design.md);
формула раздачи — [`plan_as_reservation.md`](plan_as_reservation.md);
второй режим — [`plan_specialisation.md`](plan_specialisation.md);
доли и стороны — [`plan_share_sides.md`](plan_share_sides.md).

## Специализация и сводка по товарам

**«Специализация» — второй режим плана, кнопка на странице мода**: провинция
отдаёт лучшую грамоту всем своим городам, а ячейку получает тот, кто платит
больше всех ([`plan_specialisation.md`](plan_specialisation.md)).
**Закрыта как есть, и редкость в неё не добавлять.** Конвейер тот же, что у
обычного плана, — земля, пометки город/село, лимиты, слоты, редактор поверх, —
меняется только середина.

**Сводка по товарам — иконка в окне плана**: строка на товар и причина
остановки. Она и есть инструмент, которым читается всякая правка раздачи:
столбцы «Домиков» и «Мест» — то, по чему прогон говорит, сдвинулось ли что-то.

## Четыре правила счёта, выписанные из брифа

**Never gate the plan on `generate.fed_floor`**; **the bonus counts RGOs only**;
**one method per slot**
([`production_ladder.md`](production_ladder.md)).
**A right's gate is its own `potential`, never `has_advance`**
([`town_rights.md`](town_rights.md)). **An entry is a
building and a location holds one of each**
([`whole_map_plan.md`](whole_map_plan.md)).

