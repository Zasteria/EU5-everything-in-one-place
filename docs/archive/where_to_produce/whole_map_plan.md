# The whole plan: every building, placed once, over one stretch of ground

**This is what the mod was built for**, in the owner's words on 2026-08-31, and
everything before it — the per-province answer, the three ages, the two «Считать»
buttons, the market picker — exists so that this can be right rather than
plausible.

## What he asked for

> Добавить возможность отмечать несколько нужных товаров/прав или вообще все
> сразу и видеть, какие провинции становятся «магнитами» для слишком большого
> числа зданий.

And how it is meant to be played:

> Я создаю изначальную карту со всеми запланированными зданиями сразу. Далее
> смотрю какой товар в дефиците — иду смотрю именно на этой карте где лучше
> воткнуть этот товар, чтобы не помешать другим зданиям в будущем.

So the plan is not a report, it is a **standing plan** the player consults when
the game asks a question. The shortage is read off the game's own market panel
(«Local balance», [`market_truth.md`](market_truth.md)); the plan says where that
good goes without spoiling the rest.

## The five answers, 2026-09-01

The design questions this file used to end in are answered. Verbatim where the
wording decides something.

1. **The cap is per location, not per province, and there are two of them** —
   one for rural locations, one for urban, because «количество вмещаемых линеек
   домиков в сельских и городских местах может сильно отличаться». Both are set
   in the game: «я поставил для одних 3, для других 4 — сделали расчёт».
2. **Best percentage first, and a filled province drops out for everyone else**,
   with urban rights placed before ordinary goods — *his* first guess, offered
   as a thing to test rather than a decision: «это надо тестировать… Предлагай ты
   свои варианты».
3. **No market, no price, no shortage.** «Изначально задача стоит распределить
   равномерно все товары, чтобы производилось всё в достаточном количестве.» The
   only weighting is his own, by hand, afterwards.
4. **RGOs already on the ground are supply, and they buy the plan out of
   building that good** — «если на нашей территории нет этого сырья в РГО» the
   quarries are needed, and if there is, «их нужно урезать». With the exception
   that is the reason the manual weight exists at all: wood, glass, masonry and
   stone are wanted in quantity whatever the ground already gives.
5. **A table and a map.** The table is understood; the map he left open —
   «какие у тебя есть там возможности в плане карты, так что потом разберёмся».

## What the engine allows, checked today

- **There is no building-slot cap in the game to read.** `max_levels` on a
  building is that one building's own ladder (`rural_building_cap = 1 +
  development×0.1 + max_rgo_workers×0.5 + river`, `common/script_values/`);
  nothing anywhere counts *buildings* in a location. So the cap is a house rule,
  it cannot be derived, and the mod's job is to make its consequence visible
  rather than to guess the number — see the capacity line below.
- **The map half is nearly free, because this mod already does it.**
  `bag_wtp_selection.txt` paints the picked ground from a location variable, so a
  second mode painting the plan's load is one more file of the same shape —
  `docs/research/interface.md` for what a mode can and cannot carry.
  Per-location *icons* are not among them: every map marker is a widget the
  engine instantiates against a data context of its own, so a mod may hide and
  show them but never add one. Colour, tooltip and the game's own RGO icons are
  the whole of what the map will draw.
- **CMF has the two settings this needs**: `cmm_register_numeric_setting` for
  the caps, `cmm_register_list_numeric_field` for a number per row of the goods
  list (its bounds are `default_value`, `min_value`, `max_value`, **`step_value`**
  — confirmed against CMF's own wiki on 2026-09-01), and
  `cmm_build_list_field_map` reads the whole column back as a variable map keyed
  by `goods:<good>`. **And `cmm_register_list_data_field` is a read-only column
  the mod fills** with `cmm_set_list_data_value`, which is where «how many did
  the plan give this good» belongs — beside the good, rather than as another
  number on the window's header. `docs/research/cmf.md` has the rest. The goods lists are already bool-field lists —
  multi-tick is what they natively are, and this mod suppresses it.
- **`ordered_in_global_list` takes a `limit`**, and vanilla uses it for exactly
  the shape the allocation needs (`situation_effects.txt`: strongest, then
  second-strongest excluding the first). So "this good's best free location" is
  one engine-side sort, not a walk.

## Read the formula first

**[`plan_formula.md`](plan_formula.md) is what a building is worth and who gets
the ground first**, written on 2026-09-01 when the owner called a halt to
iterating: «нам нужно сначала вывести точную и доходчивую формулу приоритетов и
выгоды». Agree it with him before writing another line of the allocation. This
file is how the thing is put together; that one is what it is trying to do.

## The design, as the thirty-third run left it

Marked where it is a proposal of ours rather than his answer. The six steps in
order, which is also what the «План» button's tooltip says:

**1. Score every good in every location.** The best method whose building may
actually stand there, that the ground feeds (`generate.fed_floor`), and that the
country could run — output times the bonus its raw materials earn. **The
buildability question is asked with `can_build_building` in the location's own
scope**, which is the rank, the terrain and `location_potential` and never an
advance, so it holds for ground nobody owns and for a plan aimed at the last age.
Without it the plan offered iron where there are no wetlands, which reads exactly
like a tool that does not rank at all. **His.**

**2. Normalize per good.** `out × (1 + bonus/100)` is in units of the good — 1.0
of lumber against 0.2 of wine — so each good is divided by its own best in this
ground, one divisor for both sides. Skipping it hands every contested location to
whatever good has the biggest recipe. **Ours.**

**2a. Then divide again, by what this province already holds of that good.**
Every location of a province scores identically for a good — the bonus is the
province's — so undivided, a good takes its best province whole and that
province's locations come out identical, which is what the thirty-fourth
screenshot showed six times over. Halving is decisive because nothing is ever
twice as good: the bonus is a ten per cent band. **Ours, and the reason is
measured in [`plan_formula.md`](plan_formula.md).**

**3. Urban rights, in towns only, every town and mandatory.** Settled 2026-09-01:
«Оно БУДЕТ выдано ОБЯЗАТЕЛЬНО. И каждый такой город обязательно получит все
здания из его бонуса.» It was all-or-nothing until then and granted one right
across six towns. Which right a town gets is asked of the town, not of the
rights: there are twelve and rarely that many towns, so a turn order would be the
whole outcome. **His, bar the per-town choosing.**

**3a. The quota, once the rights have taken their share.** Rooms left, over the
goods this ground can make, less the RGOs of that good already standing, never
below one. A good stops there and a last pass lifts it. This is «равномерно» at
both scales in one number — see [`plan_formula.md`](plan_formula.md). **His as a
rule, ours as the number.**

**4. Then the rest, in rounds, the scarce first.** A good only one location in
the ground can hold takes that place before a common good takes its second —
«жёстко зарезервировать слоты», his, and iron is the case he named. The sweeps
run in tiers of how many candidates could host the good at all: 1, 2, 4, 8, 16,
then everything, and then once more with the quota lifted. **Ours as machinery,
his as a rule.**

**5. A location holds one building of each type.** Two goods off the same
building are one answer there — but **the next location may take that building
running another method**, which is how four villages of one province take tools,
jewelry, beer and pottery one each. The rule is per location, and the province
lists that made it per province are gone. **His, both halves.**

**6. Rounds until one adds nothing**, so nothing the ground can feed is left
empty. **His.**

**A province is coherent only where it deserves to be.** Every location of a
province is worth the same to a good, so the ordered walk keeps returning to a
province it likes and its locations come out alike — an emergent property, not an
imposed one. Where the ground is tight the plan varies them, which is what he
asked for: «работать нужно точечно по локациям, красиво по провинциям должно
получаться в большой державе».

**Which locations count as towns is his to override**, from a button on the row;
no plan run clears it. And **the answer is a table and a map** — rows by province,
towns first, and a map mode painting completeness.

## What is built, and what is not

Everything in the six steps above, plus: two caps (goods per rural location, per
town), a ceiling of provinces per good (off by default), a switch for rights, two
buttons (now and the end of the game), «Пересчитать» in the window, the
town/village override, the four map pickers in the window, a row that names the
urban right and draws the building under each good, and a map mode painting
completeness.

**The demand knob, proposed and not built.** «Я выбираю товар и щёлкаю +1 и план
смещает» — under the tiers that is simply a **tier of its own, ahead of all the
others**: a number per good on the goods list, and a good with a demand of N
takes its N best locations before anything else is placed. One
`cmm_register_list_numeric_field`, one round, and it reuses the machinery the
scarcity tiers already are.

**The RGO discount is built**, as a count and not a score: one RGO already
standing is one building of that good the plan need not place, his rule of thumb
on 2026-09-01. **Not built besides:** the hand weight (his «+1 этому товару»,
which is also the exception for wood, glass, masonry and stone — under the quota
it is a multiplier on one good's share, one CMF numeric field and no new round),
regret ordering inside a tier, and choosing which goods to plan — the plan always
plans all 47.

**The country is asked now, and on both sides.** «Сейчас» scores a method only
inside `bag_wtp_avail_<n>`, so it will not offer a building whose advance is a
century away; «В конце» asks `bag_wtp_reach_<n>` instead, which is the advance's
own `potential` — what no country of this shape can ever take. Since 2026-09-03
the **charters** obey the same split: `_plan_right_gate_<k>` adds `has_advance`
unless the plan is being drawn for the end.

## Still open

- Whether the RGO count is over the planned ground only or the country too.
  Default proposed: both, since «наша территория» was his phrase.
- **Within a pass the goods are still served in a fixed order**, and the province
  divisor that used to soften it is gone (removed 2026-09-03, and for good
  reason). What softens it now is the band: two goods only tie on list order when
  both clear the same 200-wide band in the same location. Whether narrower bands
  or regret (`best − second best`) buys anything is a question for after a run,
  and a band costs a sweep.
- ~~**Iron went from offered-everywhere to offered-nowhere.**~~ **Answered by
  the run of 2026-09-03**: `iron ng=4` on Westphalia, so four locations do host a
  bog iron smelter and the gate is right. What it lost was its slot, and to
  common goods — which is fault B in `plan_gaps.md`.
- ~~Which right a province was given is not shown.~~ **Built**:
  `bag_wtp_plan_right_label`, a `customizable_localization` of the mod's own
  switching on the index the plan parked on the location.

## The trap this must not walk into

**A whole feature finished before its first load is how `where_to_produce` ended
up with six suspects and no way to choose between them** — the rule at the top of
`CLAUDE.md`, earned here. So the first thing built is the smallest piece that
shows a signal, and the signal wanted first is the cost: scoring every good over
the picked ground is 218 method readings a location where one good is about five,
and whether that survives a button press is not knowable from here.
