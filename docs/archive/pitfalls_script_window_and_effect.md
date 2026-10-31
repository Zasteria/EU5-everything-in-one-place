# Ошибки в скрипте: окно и эффект, которые обязаны договориться

Вынесено из [`../pitfalls/script.md`](../pitfalls/script.md) 2026-10-31, когда
тот ушёл за бюджет. Ничего не отменено; короткое правило осталось там, здесь —
случаи, числа и всё, что не сработало. `kb.py` ищет здесь так же.

## Окно и эффект, которые обязаны договориться

**Число и его подсказка обязаны быть одним счётом.** Столбец «Пригодность» в
поиске по грамоте считал наш `_rq<k>` -- покрытие по **доступным** способам, --
а подсказка под ним рисовала разбор перенесённой карты (`_trmm_*`), то есть
числа Construction Manager, которые про эпоху не знают. На его экране 2026-09-14
подсказка говорила «76.1 %», столбец «236.1 %», и сойтись они не могли ни при
каких данных. Он прочёл это как «бардак», и был прав: **подсказка, которая
объясняет чужой расчёт, хуже отсутствующей** -- она не просто не помогает, она
опровергает то, что стоит рядом. Перенося чужой инструмент, переноси **или**
расчёт вместе с его объяснением, **или** ни того ни другого.

**Разбор показывает слагаемые, а не итог.** «Текстиль 100 %» он читать отказался:
«а с чего бы он 100%? Я этого не вижу». Число, сложенное из покрытия сырья и
местного модификатора, обязано показывать обе половины порознь -- иначе 236 % на
земле, у которой каждый товар меньше сотни, выглядит ошибкой, а не суммой.

**A list that offers what its own button refuses is a bug report waiting.** The
swap window's right column asked whether the building may stand here and never
asked the side, while every branch of the placement asks
`_plan_is_town`; so a village building sat in a city's list and «+» on it did
nothing at all. **Build such a list out of the placement's own gate** — one arm
per (good, side), side and room and free good together — and the list cannot
promise what the press will not do.

**Two entries for one good mean two gates, and the wrong one can eat the
press.** `mason` is one of the few buildings the game allows in a village **and**
in a town, so it carries a rural and a town entry for `masonry`. Both gates read
`_pm<n>` — the town variable — and listed the same method numbers, so in a city
the rural branch matched first, called an effect that asks `_plan_is_town = no`
inside itself, did nothing, and spent the one-shot counter; the town branch never
ran and the building could not be removed at all. **Each side reads its own
variable (`_pm` / `_prm`) and carries its own side in the gate.**
