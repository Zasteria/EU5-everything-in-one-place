# Town rights: how the second window was built

Split out of
[`../investigations/town_rights.md`](town_rights.md) on
2026-09-03, at its budget. **Finished and running** — the plan grants a charter
to every town and puts its whole bundle up, and the owner has seen it: «города
получают права и домики из прав». What follows is how the window behind it is
put together, which is a fact about this mod's code rather than about the game,
and belongs beside the code. `tools/kb.py` still searches it.

---

## Built 2026-08-31, and running since 2026-09-03

The output half is in — the plan grants a charter to every town and puts its
whole bundle up, and the owner has seen it: «города получают права и домики из
прав». It is a third list on the Goods tab, exclusive with the two
goods lists, and **a second window** rather than a third line on the first --
the owner's call, and the right one, since a bundle is a different question in a
different unit. `bag_wtp_generated_rights.txt` holds the list, the per-right
pass and the slot storage; `bag_wtp_right_window.gui` holds the window, which
redeclares nothing the results window already declares.

Three things it does that are worth knowing before reading the code:

- **The pass reuses the per-good scorers.** For each good of the bundle it runs
  that good's existing `bag_wtp_score_<n>`, keeps the better of the built-up and
  village answers in a slot, and adds `price × (1 + right)` of it to a total.
  The dispatch that turns a winning method into a building, a bonus and a goods
  list runs only for the fifty provinces that take a row -- 218 methods wide is
  far too much per candidate.
- **Three fixed slots, because three is the widest bundle in the game.** Script
  has no list of tuples and the answers are flat variables on the location, so a
  row holds a fixed number of them; an empty slot hides itself on `_r_bt_<k>`.
- **`RIGHT_SCALE` is a tenth of `RANK_SCALE`.** A bundle's total is a sum of
  scaled outputs times prices and runs an order of magnitude higher than a
  single good's -- textile rights with every input present reach 64 680 against
  a method's 4 950 -- and whether the engine's fixed point ends at 21 474 is not
  knowable from here. At a tenth the worst case is 6 468 and the smallest
  difference the bonus can make is still about 4.6.

Each window draws its own global list, filled only for the question that was
asked. Both are scripted widgets and neither ever comes down, so pointing both
at one list would keep fifty rows of each alive at all times; as it stands the
closed one's datamodel is empty and the two come to 315 static widgets between
them.

**The one guess in it** is `town_rights_type:<key>` as a value a CMM list item
can hold. The game's own script writes `has_town_rights =
town_rights_type:flemish_cloth_industries_right` and the engine dump lists
`town_rights_type` as an event target, so it should store; if it does not, the
list registration is where `error.log` will say so.

