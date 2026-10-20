# Changing another mod's numbers without forking it

Learnt on `nd_unnerf`, 2026-10-14. True for any base mod whose author rebalances
in the same release as he fixes bugs.

## Telling a balance pass from a fix

Diff two versions out of git (`docs/CONVENTIONS.md`, the reference tree) and
take, per modifier key, the ratio `after / before` of every value that moved.
**A balance pass has one ratio per key**: ND 1.4.0 halved
`global_production_efficiency` in 286 places of 288, food in all 177, literacy
×0.8 in all 26. A fix has no such pattern: it changes triggers, adds keys,
retunes one object. A per-key count of ratios takes a minute and is evidence,
not a guess about what the author (or his model) intended.

## Writing the change

- Keep a table of `before`/`after` per object and path, made once from git
  (`nd_unnerf/tools/baseline.py` (мод убран 10-20, история git)); the clone keeps only one version, so the
  build cannot diff at refresh time.
- Build from the **current** base text: copy each object whole as `REPLACE:`
  and change only the numbers the table names, matched by span, so the
  author's comments and later edits survive. A value whose current number is
  no longer the table's `after` was moved again: leave it, say so on stderr.
- Direction is per key, not per sign: `cost`, `decay`, `unrest`, `separatism`,
  `inflation`, `damage_taken`, `attrition` (not `hostile_attrition`) are worse
  higher; a building's upkeep goods are a cost; `monthly_towards_*` is judged
  by magnitude; triggers are conditions, never bonuses.
- Check the output by diffing each block against the base object: the count of
  changed lines must equal the table's rows, every one a number.

Unmeasured: whether `REPLACE:` takes on advances, bureaucracies, building and
unit types and `main_menu` static/auto modifiers (`nd_unnerf/CLAUDE.md` (мод убран 10-20, история git)).
