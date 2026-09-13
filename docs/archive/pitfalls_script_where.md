# Ошибки в скрипте: где что живёт, и что молча не читается

Вынесено из [`../pitfalls/script.md`](../pitfalls/script.md) 2026-09-14, когда
тот ушёл за бюджет. Ничего не отменено — это первые правила того списка, самые
общие: где обязан лежать триггер и где значение, что получает фильтр типа
зданий, и почему один предикат в двух местах разъедется. `kb.py` ищет здесь так
же.

## Где что живёт, и что молча не читается

**Two script values of the same name: the first wins, the second is dropped
silently** — the rule `customizable_localization` obeys too, and it costs the
same way: the wrong copy edited, nothing said anywhere. Two shipped in one day
on 2026-09-06. **`check_script.py` reports them now**, and the same folder rule
holds for both neighbours: a trigger lives only in `scripted_triggers`, a value
only in `script_values`, and each cost a run before its checker existed.

**A `building_type` filter receives the object as `this` — not `scope:target`,
and not `root` either.** Vanilla's `58_building_type.txt` promises both and has
neither: reading `scope:target` logs an error on every pass of the list, and
reading `root` logs nothing and matches nothing, which is worse. Measured
2026-09-09 — a chip on `target = root` left the list empty while its probe held
the location and the list it read was populated on 454 locations; the only other
`root` reader here is `rgo_bonus_filter`'s location-panel pair, the one that had
never worked; `06_country.txt` says "root is player" in its own header. **Ask
`this` before any scope change**, literal on the far side, one `AND` branch per
object — a generator's job. `building` and `location` scoped filters do get
`scope:target`.

**One predicate in two places will drift, and the copy that decides is the one
nobody edits.** `_reach_<n>` — "could this country ever have this method" — was
computed twice: once to write the trigger, once to decide whether to ask it. The
writer learnt about `country_potential`; the asker did not, so 429 triggers were
generated correct and never consulted, and a Tibetan atelier stood in Westphalia.
Both now call `method_gates`. The symptom is the worst kind: the fix looks
present in the generated files.

**A partial report read as a whole one is a wrong answer with a number attached.**
`WTP BLDG ... built=0` covers only *multi-good* buildings; concluding "no foreign
building was placed" from it was reading an absence in a subset as a fact about
the plan. The rule this repository already has — an empty result is a fact about
the tree, never about the game — applies to its own diagnostics too.

**`local_<x>_building_levels` names a building, not a good — and the two look
alike.** `local_fine_cloth_guild_building_levels` raises the level cap of
`fine_cloth_guild`; stripping `_guild` turns it into the good `fine_cloth`, and
the charter then reads as "favours fine cloth" and pulls in every building that
makes it — a Tibetan atelier the bonus will never touch. Caught by the owner on
2026-09-09. A per-building bonus has to stay attached to its building: derive the
good from the building, and gate on the winning method being that building's.

