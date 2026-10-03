# `where_to_produce` — what has been tried and must not be tried again

**A `flowcontainer` carrying a `datamodel`, 2026-09-04 — four builds, four
crashes, five of his runs.** The editor's picker wrapped on one. Every build with
it died (twice on opening, once on opening with a switch that could not help,
once on loading the game); both builds without it opened. Nothing was ever
logged. Vanilla has no such widget anywhere — a wrapping grid of a list is a
`fixedgridbox`. `check_script.py` refuses the pairing now.
`../pitfalls/interface.md`.

**The three things reverted while chasing it were innocent**: a variable map
keyed by `goods:clay`, the same map keyed by a flag from `Goods.GetKey`, and 47
written-out cells with `ScriptValue` in their localization. The count per good in
the picker is **not** on this list — it was never shown to be the problem, and it
can be built again once the picker is known to open.

**And the process failure that made it cost four sessions instead of one:**
`c14aa0f` introduced the flowcontainer and **was never loaded**. Each session
after it took «the last build worked» from the run before that one and hunted in
what it had added since. **A build nobody ran is not a baseline.**

Split out of [`../../mods/where_to_produce/CLAUDE.md`](../../../mods/where_to_produce/CLAUDE.md)
on 2026-09-03, at its budget. Every line here is a thing that was built, run and
reverted; the brief keeps the one-line pointer and this keeps the reasons.
`tools/kb.py` searches it.

---

**Not to be attempted again:** a geography tree of our own (empty twice), gating
charters on their advance (`plan_gaps.md` H), spreading charters inside a province
(it emptied a province of the charter its ground was made for), answering a
preference with a re-plan, and reopening why a scarce good has one building —
**it is the RGO discount, measured twice** (B). `bag_wtp_register` destroys
nothing (`docs/PITFALLS.md`).


Where each is argued out: `docs/archive/where_to_produce/plan_gaps.md` for the charter age
gate (H) and the RGO discount (B), `plan_formula.md` for the editor against a
re-plan, `whole_map_plan.md` for the geography tree, `docs/PITFALLS.md` for
`bag_wtp_register`.

---

# Отклонено 2026-09-04, при разборе теории редактора

## Целевое число домиков вместо «+1»/«−1»

Предлагалось заменить «−1 / +1» на «хочу N домиков». **Отклонено, и он прав.**
Цель в N домиков — это до N−1 перемещений чужих домиков за одно нажатие, а
требование ровно обратное: «не хочу, чтоб домики катались и перестраивались
кучами».

Не путать с уже отклонённым «весом товара в перепланировке»
([`../archive/wtp_not_again.md`](wtp_not_again.md)) — то была другая
идея с тем же исходом.


## Режимы, которых он не захотел

**Отклонено:**

- **«Что строить здесь?» отдельным режимом** — ваниль это уже умеет: локация →
  строительство → сортировка по производительности.
- **Цена области.** «Обычно тебя мало волнует ценность земли. Ты будешь брать
  всё, что тебе нужно, и как правило вообще не по причине самой земли.»
  Мод нужен ровно затем, чтобы **не думать** о земле, которую и не хочется
  обдумывать.
- **Сравнение двух слотов** — назначения не нашлось.
- **Связывать поиск и план на выходе.** Это два разных инструмента: поиск —
  точечный, для игрока, который делает своё и хочет данных; план — «функция для
  ленивых, кому нужно подать оптимальный, быстрый и удобный готовый вариант».
  Вместе не используются.

## Упаковка двух ключей в одно `order_by`-число

Предлагалось для равномерной выемки при «+1»: `превышение доли × K + выгода`.
Отклонено в пользу двух проходов — предел фиксированной точки движка отсюда не
известен, и предупреждение об этом уже стоит в коде при `_plan_order`.
