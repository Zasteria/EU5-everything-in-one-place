# Settled — do not measure any of this again

**This is the one document worth reading in full, and it is short.** Every row
cost the owner an evening. Asking for any of it a second time spends the one
resource this repository cannot generate for itself: only the player can run the
game.


| question | answer | where |
| --- | --- | --- |
| What is settled about the widget leak? | **Eight rows of it, in the file that owns them** since this one outgrew its budget. The short of it: it is the base game's, and no pool to raise. «Мод не может освободить виджет» — **неверно, и это доказано в игре 2026-09-19**: `PdxGuiDestroyWidget` из мода работает. Чего всё ещё нет — способа перечислить детей, поэтому уничтожить можно только названное. | [investigations/widget_leak.md](investigations/widget_leak.md) |
| What was settled about the localization errors? | Three rows, closed in August and moved out when this file outgrew its budget. | [archive](archive/settled_localization.md) |
| What else is closed and out of this file? | Семь строк (включая окно выбора на карте у `where_to_produce` и бонус РГО у здания с двумя слотами производства): `glorpui_hints` loading, buildings upgrading in place, the two market-balance answers, and the age filter. | [archive](archive/settled_closed.md) |
| What is settled about `where_to_produce`'s plan? | Two rows, closed by the 2026-09-02 and 09-07 runs and moved out when this file outgrew its budget: why glass went to villages (a ticked rank *is* the rank for the whole calculation), and that the plan is not uneven and reservation moved nothing. | [archive](archive/settled_wtp_plan.md) |
| Чем Construction Manager тормозил игру? | **Всегда живым деревом по всем типам зданий в его скрытом окне, и ворота на этом дереве потолок снимают — прогон 09-18.** Кадры тут не при чём: на паузе CM стоил 15% FPS, а потолок держался на любой скорости и не двигался галочкой максимизации тактов. Ворота — то же выражение, что уже стоит на драйвере дерева; правка в `mods/cm_perf`. | TESTLOG 2026-09-18 |
| Можно ли тормозить значки отрядов через `max_update_rate`? | **Нет, два прогона 2026-09-20.** Свойство портит **попадание мышью**: значки рисуются, рамочное выделение работает, щелчком отряд не выбрать. Семь типов, потом три — без кнопок и без раскладки — **разницы никакой**, значит ломает любой потомок значка. Свойство настоящее (игра ставит его раз, FUM двадцать), но только на то, по чему не кликают. | TESTLOG 2026-09-20 |
| What does `can_build_building` answer, and where? | **Two different questions in two scopes.** In a *location's*, the rank, terrain and `location_potential` — never an advance, which is why the buildable tick filters on the location and not the owner. In a *country's*, the advance. | TESTLOG 2026-08-31, 17th |
| Do the town/village ticks reset themselves? | **No, measured.** The ones he cleared read 0 through a window close and a map change; the fourteen that «came back» are other locations, ticked earlier and outside the ground on screen, which widening it brought in. **A tick is a location variable and outlives a save** — hence «Сбросить пометки», all five continents at once. | TESTLOG 2026-09-02 |
| What is settled about the plan editor's window? | **Five answers, in the file that owns them.** A `flowcontainer` with a `datamodel` crashes the game silently (four builds); a wrapping grid of a list is a `fixedgridbox`; a goods datamodel row reaches no numbered counter, so a cell printing one is written out; `And(...)` in a GUI expression is eager, so a `visible` guards nothing; a variable read on the wrong scope is quietly false for ever. Two are checkers. | [pitfalls/interface.md](pitfalls/interface.md) |


## Decisions that are closed

**And one thing the owner has already rejected as an answer:** "report it to
Paradox". They know it is a base-game defect and know other players have it. The
job is to find something that helps from the mod side, or to establish with
evidence that nothing can.

**Why `nd_ru` exists next to a 93% machine translation.** `nation_destinies_rus`
is Google's, and it lags the base mod's versions. The owner loads `nd_ru`
*after* it on purpose: where ours has a key, the human translation wins;
everywhere else the machine one fills in rather than English. This was decided
before this repository existed and **has now been asked twice**. Do not propose
dropping `nd_ru`, and do not propose reaching 93%. The measurement behind it is
in [`archive/nd_ru_and_the_machine_translation.md`](archive/nd_ru_and_the_machine_translation.md).

**`glorpui_hints` ships Russian and hands the other ten languages back.**
Settled 2026-08-30, the owner's call: he prefers this mod's Russian to Glorp
UI's copy of it and does not mind about the rest. `SHIP_GLORP_HINTS` is
`["russian"]`. Also his call: the two «показать всё» switches stay independent.

**The reference tree is there to be used.** Reading, grepping, quoting and
copying out of `reference/` into a mod is settled — see
[`../reference/README.md`](../reference/README.md). Do not stop mid-task to ask
about it, and do not report a mod arriving at a newer version as a problem: that
is the normal state of the tree.

**Nothing about updating the owner's mods may require a session of ours.** He
asked for that in those words. `mods.bat` is the menu; do not build a step only
a session can perform, and do not tell him to run the pieces by hand when the
menu covers it.

## What has never been run

Kept as one list in [`TESTLOG.md`](TESTLOG.md#never-run) rather than scattered
through prose. Check it before calling anything confirmed.
