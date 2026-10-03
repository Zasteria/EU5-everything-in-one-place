# The building ladder, and why one answer is not enough

The owner's question, 2026-08-31: *the first half of a game changes little, but
from the third age buildings improve constantly. Can I plan for the whole game
by turning the age filter off, or does that want thinking about separately?*

Turning the filter off does give the last age's method — and gives only it. The
answer below is that "best now" and "best at the end" are two different
provinces often enough to be worth two columns, and that the game hands us the
ladder for free.

## The ladder is `obsolete`, and it is the game's own

`building_types/readme.txt`: *obsolete: <building type> what building type this
one makes obsolete*. Thirty chains, every production one ending in a mill or a
factory:

    weapon_guild -> weapon_workshop -> weapon_manufactory -> weapon_factory
    cloth_guild  -> cloth_workshop  -> cloth_manufactory  -> textile_mill
    paper_guild  -> paper_workshop  -> paper_manufactory  -> paper_mill

Output along a rung: 1.0 -> 1.1 -> 2.0 -> 4.0. **Methods are almost never gated
themselves** — ten of them carry `unlock_production_method`; the other 218 ride
on their building's own advance, of which 184 buildings have one.

Two facts that made the feature cheap:

- **A building somebody obsoletes can never be the endgame answer.** 76 of them
  are; 94 methods of 228 survive. Checked at full bonus over every good and both
  sides: no obsoleted method beats a surviving one, ever. So "the best of the
  survivors" needs no age arithmetic at all.
- **The location requirements do not move along a production chain.** All thirty
  chains compared on `town`, `city`, `port`, `potential`, `can_build`: only
  `charcoal_maker -> improved_charcoal_maker` and two military chains differ.
  Where a guild can stand, its mill can stand. **So the ground never expires —
  what expires is the recipe.**

## What moves is the input mix

The bonus is `10 * (inputs the province supplies) / (all inputs)`, so the
province's rank follows the recipe's inputs, not its output. Fourteen of the
forty-two goods shift their mix along the ladder; five change it outright:

| good | first rung | last rung | ceiling |
| --- | --- | --- | --- |
| `firearms` | bronze: copper + tin | lead + saltpeter | 6.66% -> 4.45% |
| `cannons` | copper + tin | lead + saltpeter | 5.46% -> 3.48% |
| `fine_cloth` | silk | dyes | 10.00% -> **0.63%** |
| `paper` | cloth + lumber | pure lumber (wood pulp) | **1.66% -> 10.00%** |
| `weaponry` | lumber, coal, tools | steel, coal, lumber | 5.24% -> 8.10% (age 3) -> 3.75% |

The other twenty-eight — cloth, leather, beer, furniture, pottery, tools — keep
their mix and only grow, and for those one column would have done.

`weaponry` is the one that is not even monotone: the age-3 workshop is the best
place in the ladder and the age-6 factory is the worst, because steel is a
produced good and carries weight in the denominator no RGO can ever supply.

## What was built on it

A second answer per side, `bag_wtp_end_*`, found in the same walk: a survivor's
`bag_wtp_m<n>` is computed once and offered to both columns, so the far column
costs a comparison per method rather than a second pass over the province. It is
**written only where it differs from the near one**, so an empty cell is the row
saying "this province does not change" — which is what the twenty-eight stable
goods will say, and the point of showing it that way.

`bag_wtp__rank_by_end` decides which column the ranking sorts on. It matters
more than it looks: the near column decides which fifty provinces get a row at
all, so with the tick off a province that is poor now and first at the end is
never seen. **That is the known hole in this feature** and the reason the tick
exists.

## Two things the eighteenth run turned up

**A recipe the ground cannot feed is not an answer.** Fine cloth in the
Carpathians came back as one row: silk weavers at 0.00%, in a country whose
provinces are full of wool. The arithmetic was right — silk weavers make 0.70 a
level and wool weavers 0.50, so 0.70 unfed beats 0.55 at the full ten percent —
and the answer was still wrong, because the game would run the recipe the market
can feed and the market is fed by the ground. The pass now keeps a method only
where the province supplies at least one of its raw materials, asked as
`_try > <the method's unbonused output>`: a literal, and the smallest step any
raw material makes is 0.56 across all methods and 1.9 in the endgame set, so it
never turns on rounding. Where nothing is fed there is no row, which is what the
zero-bonus filter did with those rows anyway.

**A ladder can end early, and then the far column is 0.00% rather than blank.**
Fine cloth from wool has no rung above the workshop: `fine_cloth_manufactory`
and `fine_cloth_mill` take only silk or cloth. So in a wool country the fed
answer for the last age is *nothing*, and the nineteenth run got a column that
was blank almost everywhere — which had meant "this province does not change"
the day before. The far column now always prints something: the best survivor
the ground feeds, or, where it feeds none, the best survivor at 0.00%. Only the
fed figure reaches `order_by`, so an unfeedable mill can be read off a row and
can never rank one.

**Eight buildings run two methods at once, and the mod models one.** A building
may carry more than one `unique_production_methods` block, and each block is a
slot: the building runs one method from *each*, not one in total.

| building | slot 1 | slot 2 |
| --- | --- | --- |
| `fine_cloth_guild`, `_workshop` | the weave: silk, wool, cloth | the finish: dyes, alum, fur |
| `fine_cloth_manufactory` | silk or cloth | dyes, or dyes + alum |
| `cannon_maker`, `cannon_workshop` | the barrel: bronze, iron, wood | the ammunition: stone, lead, iron |
| `gun_smith`, `guns_workshop` | the gun | the ammunition |
| `jewelry_guild` | 3 ways | 4 ways |

So a fine cloth guild on silk and alum makes 0.7 + 0.2 a level and wants silk,
alum and dyes; the mod says 0.7 and silk. It understates the output and the
inputs of exactly the eight, and the owner named all three families of them
unprompted from playing.

The shape of the fix is cheap and already fits: generate the **combination** of
the slots as one synthetic method — nine for a cannon maker, twelve for a fine
cloth guild, about seventy across the eight — with the outputs summed and the
inputs merged, and print the pair.

**What is not cheap is knowing whether the merge is what the game does.** The
bonus is `10 * supplied / all inputs`, verified against three tooltips, all of
them on buildings with one slot. With two slots the denominator is either the
union of both methods' inputs or one method's alone, and the two give different
percentages. One hover on a fine cloth guild's build panel settles it, and until
it is settled the combination is not worth building — a wrong denominator would
be wrong on the eight buildings a player cares most about.

## Not answered here

- **Whether a building upgrades in place or has to be rebuilt.** `obsolete` says
  only that the old one can no longer be built. If the game rebuilds a chain in
  place, the whole question is milder than the owner thinks; if it does not, the
  far column is the only one worth planning on. One look at a guild in a country
  that has reached the workshop settles it.
- **Level rights and the ladder together** — deferred with the rest of the level
  rights in [`town_rights.md`](town_rights.md).
- **The rights window has one column still.** A bundle's ladder is three
  ladders, and nothing about the shape above says how to show that in a row.
