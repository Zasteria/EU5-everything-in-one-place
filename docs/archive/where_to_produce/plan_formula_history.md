# Формула плана: то, что уже решено и объяснено

**Вынесено из [`../investigations/plan_formula.md`](plan_formula.md) 2026-09-06, когда тот перерос бюджет.** Здесь две законченные части: что говорит собственная игра владельца и чем она расходится с планом, и почему «равномерно» и специализация — два разных вопроса. Обе объясняют **почему** правила такие; сами правила живут в коде и в оставшейся половине файла.

## What the owner's own play says, and where it differs

He described it himself, and marked it as his habit rather than as correct:
province by province, the top three buildings by local bonus in the town, then
the same in the countryside, then a rural location set aside to feed the
province; iron and its like displace a top-three building where nowhere else will
hold them; and when a right arrives, its bundle replaces the three.

## Равномерно and specialisation are two different questions

**Settled 2026-09-03, and the confusion was the session's, not his.** «Равномерно»
is *how many* — the quota, rooms ÷ goods — and specialisation is *where those
land*, which nothing in the quota resists. Two divisors did resist it and both are
gone: one halved a good's second building in a province, the other made the
charters' ranges disjoint. What that cost and what he said about it is in
[`../archive/plan_formula_evenly.md`](plan_formula_evenly.md).

**The problem he cannot solve by hand is the one the formula exists for.** Doing
it province by province maximises each province in isolation, and the goods that
gain nothing anywhere are left with nowhere at the end — «а вдруг у меня вообще
нет каких-то РГО, например того же песка?». Dealing in bands over the whole
ground is the same greed, ordered globally instead of locally, and that is
precisely the difference between his hand play and an optimum.

**Not yet in the formula and named by him:** a rural location per province set
aside for food. He said «до этого мы пока ещё не дошли».

## Urban rights, and why they are their own pass

A right is a `location_modifier` on the town:

```
royal_masonry_rights = {
    location_modifier = {
        local_masonry_output_modifier = 0.25
        local_glass_output_modifier   = 0.25
        local_production_efficiency   = town_right_efficiency_penalty
    }
}
```

So it is **two things at once**, and the owner had it right: «права дают слишком
жирный бонус и дебафят всё остальное». The bundle's goods get +20% to +50% output
where the whole RGO ceiling is 10%; and *everything else in that town*, bundle
included, takes a blanket production-efficiency penalty.

Two consequences, and the first is a hard one:

- **a town holding a right should hold its bundle and as little else as
  possible.** A non-bundle building there earns the penalty and none of the
  bonus, so the same building is strictly better in a town without a right. The
  bands must therefore discount a right-holding town's leftover slots;
- **rights are worth more than anything the bands can find**, by a factor of two
  to five, which is why they are dealt first rather than competing.

**`town_right_efficiency_penalty` is a define and it is not in `reference/`** —
only its eleven uses are. The structure above is certain; the number is not, and
it is one `grep` on the owner's install. Until then the discount above is a
direction without a size.
