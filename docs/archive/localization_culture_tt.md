# A pattern in the data is not a fault

Moved out of `docs/pitfalls/localization.md` when it hit its budget, 2026-10-04.

**A pattern in the data is not a fault until something fails.** All 1755
`*_culture_tt` keys in the game's Russian
`EU5_customizable_localization_ru_culrel_l_russian.yml` hold a bare number that
is exactly the key's own line number minus two — every one of them, plus 624
more in a sibling family. They are used as `#TOOLTIP:CULTURE,$X_tt$,`, where a
culture key looks like it belongs. That is a striking, verifiable pattern and it
reads exactly like a generator that wrote line numbers into tooltip targets, so
this document briefly said every culture tooltip in the Russian localization was
broken.

It is not. A hover settled it: the tooltips are complete and correct, and the
key on screen (`westphalian_cadj` → `#TOOLTIP:CULTURE,$westphalian_tt$,` →
`"1052"`, on line 1054) is one of the numeric ones. The number is what the engine
wants there, or the engine ignores it.

The cost of getting this wrong would have been 1755 keys rewritten to fix
nothing. **A pattern explains a fault; it does not establish one.** Before
repairing on the strength of a shape in the data, find the thing that visibly
fails — and if nothing visibly fails, that is the answer.
