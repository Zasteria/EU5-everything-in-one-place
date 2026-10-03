# The plan's formula: what is being maximised, and how the ground is dealt

**Rewritten 2026-09-01, when the owner stated the objective outright.** Before
this the file was a pile of rules; it is now a derivation, because he said what
the plan is *for* and everything follows from that.

> Товары будут добываться все которые только можно добыть, но распределение их
> должно быть такое, где максимально возможная часть получит свои «плюшки», а
> другие получат чуть меньше или вообще не получат.

That is an optimisation problem with a covering constraint, and it has one
answer.

## The problem, exactly

Over the chosen ground, choose a building for every slot so as to

**maximise** the total bonus captured,

**subject to**, and none of these are negotiable:

1. **every good the ground can produce gets at least one building.** «Все товары
   которые можно произвести на выбранной земле — должны производиться, все. И не
   важно есть для них сырьё на этой земле или нет.» Coverage is a hard
   constraint, not a preference;
2. one building of a type per location, and `can_build_building` must allow it;
3. `load(L) ≤ cap(L)`, the owner's house rule — the game exposes no slot count;
4. every town takes its best urban right and its whole bundle is placed there.

## The currency, and why it is not what the file used to say

**A raw bonus does not compare across goods.** Measured over all 47: the ceiling
a good's best recipe could ever reach runs from 2.00% to 10.00%, and five goods
are capped under 5%. A good that can never earn more than 2% will lose every
comparison against one that can earn 10%, and that is not a reason to build it
somewhere worse.

**A normalised `worth` does not compare either, and that was the older mistake.**
Dividing each good by its own best *on this ground* squeezes everything into
0.909–1.000 — because the bonus is only a ten per cent band — and then the
outcome is decided by the goods list's arbitrary order. That is what produced six
identical villages on the thirty-fourth run.

What compares is **how much of what this good could ever get here, it gets**:

```
gain(g, L)  =  bonus(g, L) ÷ ceiling(g)          ∈ [0, 1]
```

1.00 means "the ground feeds this recipe completely". 0.00 means "it feeds it
nothing", which is still a building the plan must place. **The objective is
Σ gain over every building placed**, and no price, no output size and no
per-good divisor enters it. It is the honest reading of «свои плюшки».

## The one insight that makes the deal optimal

The failure mode is greed, and the owner named it: «дальше не жиреть». If every
good takes its own best location in turn, the good that would gain 0.9 there and
the good that would gain 0.1 there compete on equal terms, and whichever the list
reaches first wins. Total gain is thrown away for nothing.

The fix is opportunity cost — place a good where what it gains most exceeds what
it displaces — and the cheap way to get it is **not** to compute it per location.
It is to deal the ground in descending order of gain, across all goods at once:

```
for band in 1.0, 0.9, 0.8, … 0.1, 0.0:
    for each good, scarcest first:
        if it is still under its quota:
            take its best free location whose gain ≥ band
```

By the time a good with gain 0.2 reaches a location, every good that would have
gained 0.9 there has already taken it. **The ordering is the opportunity cost**,
and it costs one comparison on a walk that already happens.

Three things the owner asked for fall out of it without a rule of their own:

- **the best bonuses are taken first**, whichever good they belong to;
- **a good that gains nothing anywhere places only in the last band** — that is,
  in the ground nothing else wanted. «Выделить у менее вкусных провинций место
  под всё остальное»;
- **nothing is left to the goods list's arbitrary order** except among placements
  of genuinely equal gain.

## The rest of the deal, in order

| # | pass | why |
| --- | --- | --- |
| 0 | **what the owner weighted by hand** | his knob; not built |
| 1 | **urban rights**, every town, whole bundle, five bands with a quota on all of them | the largest number in the game — see below |
| 2 | **coverage**, five bands: every good takes one location, its own best | constraint 1, guaranteed |
| 3 | **the scarce**, tiers of 1/2/4/8/16 candidates, five bands inside each | «зарезервируйте их под железо» |
| 4 | **everything**, five bands | the objective, and the bulk of the plan |
| 5 | **surplus**, five bands, quotas raised a layer a round | fills what is left, still by gain |

**Pass 2 is the guarantee and it is not optional, and it runs before the bands
rather than after them.** A good that would lose every band — because rights took
the towns, or because it gains nothing and the ground filled — takes its own best
location first. It was pass 31 of 32 for one day and placed **nothing**: the
ground was 192 of 192 full by the time it ran.

**Pass 3 is a phase and not a rung inside every band, and that is the correction
of 2026-09-03.** A scarce good could only claim a location where its gain cleared
the band it was under — and a scarce good's gain is usually low, because scarcity
and a poor recipe have the same cause. Measured: the tier rungs of all five bands
placed three buildings of sixty-nine. Reserving means finishing before the common
goods start; the bands inside the phase keep gain deciding between two scarce
goods, so the rule is weakened only across that one boundary.

**Every ladder is banded, the last included.** It was one pass at band 0, where
gain does not enter at all, and on a large ground that one pass placed 271
buildings of 770 — more than a third of the plan decided without the objective.

**And pass 5's band is each good's own best, not the absolute one.** This is the
one place the objective is deliberately not maximised, and a 416-location run is
what bought it. There the quota came to 29 a good and nothing reached it — cannons
had a quota of 160, could stand in 103 locations and got **two** — so the band was
the entire allocator and, being absolute, it sorted the goods by their ceiling
rather than by their fit: the 30 goods that touch 1000 somewhere averaged 42
buildings, the eight that never do averaged 12, against an even share of 36.

The distinction that makes it principled: **the absolute band deals the fair
share, where the ground is contested and the biggest gain should win the room; the
relative band deals what is left, where handing every leftover to the largest
ceiling is not opportunity cost but concentration.** A good whose best on this
ground is 362 enters `open800` at 290 — its own top fifth — exactly as cloth
enters at 800.

## Three questions the owner asked of this order, 2026-09-06

He described the plan back to me as «сначала грамоты, потом городские домики до
ровного лимита, потом сельские». **The first step is right and the rest is not,
and the difference is worth stating plainly.**

**There is no town phase and no village phase.** Nothing in the plan ever fills
one side and then the other. What separates the passes is only two things: **how
few locations can host a good** (the tiers) and **how much the ground pays**
(the bands). A town building and a village building are placed in the same sweep,
by the same rule.

**«Где угодно» goods are not squeezed in at the end.** They are in every pass on
the same footing; what the tier ladder does is make them *wait* — a good that can
stand in forty locations is not scarce, so it places after the ones that can
stand in one. Then the `tierall` passes place the bulk: on his run they took the
plan from 57 buildings to 117 of 150, and most of that is exactly those goods.

**Bog iron has two guarantees, and both come before the common goods.** The
covering ladder (passes 2) gives *every* good that holds nothing one building at
its own best location — that is the hard constraint, and it runs before any band.
The scarce ladder (pass 3) then lets a good that can stand in at most 1, 2, 4, 8
or 16 locations finish before common goods start. On his run iron could stand in
**4** locations and ended with **4**: it took every place it had.

**What the share does through all of this** is bound each good from above; it is
not a step in the sequence. And the surplus pass at the end is where the spread
he still sees comes from: on that run 33 of 150 buildings (22 %) were dealt after
every quota was met, by gain alone — which is why cloth ends at 15 against a
share of 5.

## What is not the formula's at all: the editor

**A preference is not a term in the objective, it is an edit afterwards.** That
was learnt the expensive way. A hand weight fed back into a full re-plan was
built first and measured at **42 locations of 48 moved** by a knob meant to move
one — «Мод не пересобирает весь план с 0, он просто точечно выбирает какой товар
X менее болезненно удалить для наилучшей установки туда товара Y».

So the plan is state, and `bag_wtp_edit_*` changes it in place: every candidate
is asked what one more of a good would cost there (nothing where a room is free,
otherwise the gain of the cheapest building that may come out), the cheapest wins,
and exactly one building moves. **Two buildings are never the victim** — a good's
last on the ground, which keeps the covering constraint through any amount of
editing, and one belonging to the bundle of the charter granted in that town.

**Which means the objective in this file stays a description of the formula
alone.** His Sauerland complaint — five naval charters in seven towns where he
wanted a mix — is the formula maximising what it was told to maximise, since the
charter is worth 1000 there against weaponry's 163. Spreading charters *inside a
province* was tried and reverted for emptying a province of the charter its ground
was made for. That is an edit, not a rewrite.

One damper keeps a pass from stacking, and it is the share. **It is not a phase**
— it is the ceiling every good carries through all five passes, and the pick tests
`_pn<n> < _pq<n>` and nothing else.

**Since 2026-09-06 it knows three classes of good and two kinds of room**, because
they do not mix: a town-only good cannot take a village room however many there
are. Three ceilings, and the smallest names whoever runs out first:

```
town   =  town rooms    ÷ goods that can stand only in a town
village=  village rooms ÷ goods that can stand only in a village
all    =  every room    ÷ every good the ground can make
level  =  the smallest of the three
```

If `all` is smallest the ground ran out at once and everybody shares one number,
as before. If a side is smallest **its goods freeze at that level, their rooms
leave the pool, and the rest get a second level**:

```
rest  =  (every room − level × goods of the saturated class) ÷ the other goods
```

Then, per good, `max(1, its class's level − rgo(g))`. Two levels are enough:
there are three classes, and once one is frozen the other two share what is left.

**Measured on his ground, 2026-09-06**: 6 towns (24 rooms) against 15 town-only
goods gives 1.6, so the town side binds at **1**; the other 23 goods get
(150 − 15) ÷ 23 = **5**. All fifteen town-only goods came out at exactly 1. The
old one-pool formula said 3 for everyone — a number the towns could never pay.

It is «равномерно» and it is scale-free: three provinces give a share under one,
so everything is covered once and mixed; a large realm gives a share of
twenty-odd, so each good takes its best twenty-odd places and stops.

**A charter's buildings are spent out of the good's share, not added to it** —
changed 2026-09-03, and the owner's arithmetic is why. It read

```
quota(g)  =  max(1, free ÷ |goods| + charters(g) − rgo(g))
free      =  capacity − everything the charter round already placed
```

and on Westphalia `free ÷ |goods|` is 84 ÷ 35 = **2**. Wine, whose charter is
brewing, walked in at 2 + 6 = **8**; iron, with two RGOs under it, at 2 − 2 = 0,
floored to **1**. He read the result off the report and did the arithmetic
himself: «как будто бы 1 домик + 2 РГО не равняются 9, а равняются 3. Так почему?
Почему РГО внезапно стал весить 4 вместо 1?» Nothing was wrong with his rule —
one RGO is one building — and everything was wrong with the number it came off.
Now the share is 192 ÷ 35 = **5**: wine walks in already holding 6 and takes no
more, iron gets 3.

**What that overturns.** `charters(g)` was added after the thirty-eighth run,
where `tools` held six charter buildings against a quota of 2 and so could not
take a free room in Sauerland at a gain of 799. Against a share of **2** that was
a real fault; against a share of **5** a good already holding 6 is above its
share, and stopping there is the evenness rather than a bug. The old fault cannot
recur, so the old fix is gone with it.

**There was a second damper, `gain ÷ (1 + already in this province)`, and it is
gone** — removed 2026-09-03, for the reason under «Равномерно and specialisation»
below. Nothing divides the gain now, and the counter behind that divisor is not
written either.

**Read `q` in the report against this and not against `PASS quota`.** It is read
back after the plan, so it carries the layer the surplus ladder added to it — one
per sweep — on top of the number above.

**The allocator is what charges the charters to the share.** `_pn<n>` counts
every building of a good, the charter round's included, and the pick tests
`_pn<n> < _pq<n>` — so no subtraction is needed here and none is done. Doing it
in both places is what charged them twice.
Without that term a good the charters favoured could not place one building of its
own — 2026-09-03, `tools` at six charter buildings against a cap of two, locked
out of a province paying it 799 of 1000.

## Грамоты — свой проход, и он первый

Разбор целиком (почему связка неделима, почему квота — уровни, а не потолок, и что стоило прогонов) переехал в
[`../archive/plan_formula_history.md`](plan_formula_history.md).
Короткое правило: **грамота выдаётся до всякого обычного товара, целой связкой, и каждый город плана получает ровно одну** — `town_rights.md` про её ворота.

## Что вынесено

**Что говорит его собственная игра**, и **почему «равномерно» и специализация — разные вопросы**: две законченные части переехали в
[`../archive/plan_formula_history.md`](plan_formula_history.md); `kb.py` их находит.

## What only a run can settle

- the value of `town_right_efficiency_penalty`, and therefore how hard the bands
  should discount a right-holding town's spare slots;
- whether a cap of 3 is right, which is why he asked for 3, 4 and 5;
- whether the bands want ten steps or four — a band costs a sweep.
