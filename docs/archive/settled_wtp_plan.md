# Settled — план `where_to_produce`, две закрытые строки

Вынесено из [`../SETTLED.md`](../SETTLED.md) 2026-09-18, когда тот вышел за
бюджет. Оба вопроса закрыты прогонами и **повторно не меряются**; `tools/kb.py`
ищет и здесь.

| question | answer | where |
| --- | --- | --- |
| Why did the plan put glass in villages and never in a town? | **Because most of those «towns» were villages ticked into towns, and a guild is `town = yes`.** `rural_glassmaker` is `rural_settlement = yes, town = no`; both carry the *identical* sand-in-market condition and it passes. Measured on twenty goods at once: sixteen with no market condition at all were stopped in the same 3-of-17. **And the tick is the rank, for the whole calculation** — «расчёт должен симулировать ранги… и не важно что там стоит на самом деле», so a ticked location is scored, granted rights and built on as what it was ticked into. `bag_wtp_stands_<building>` takes the rank from the tick, the potential still from the game. | TESTLOG 2026-09-02 |
| Is `where_to_produce`'s plan uneven, and would reserving locations fix it? | **No, and no — 416 locations, 2026-09-07.** Nineteen goods end one or two below their own quota — **stopped by the quota, not by the ground** — and stand at 60–65 counting the RGOs already there, which is his own rule: `stone` is 45 + 15 = **60** against `beer`'s 61, so its nineteen unused villages are ones it does not need. Short only `salt` 53, `iron` 51, `fish` 39, `naval_supplies` 38, and all four for want of ground. **Reservation by tightness fired at full strength and moved nothing; removed.** | TESTLOG 2026-09-07 |
