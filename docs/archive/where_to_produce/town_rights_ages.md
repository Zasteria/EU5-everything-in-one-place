# Urban rights — the ages, and the two cloth charters

Split out of [`../investigations/town_rights.md`](town_rights.md)
on 2026-09-03 when it outgrew its budget. Both questions are settled; kept
because what they measured about the game stands.

## The ages, read off the advances on 2026-09-02

They settle a question that had been answered from memory, and the owner's
reading of it was right:

| what | advance | age |
| --- | --- | --- |
| all nine general rights | `town_rights_enable` | **3, Discovery** |
| first firearms building, `hand_cannon_guild` | `hand_cannon_guild_advance` | 1, Traditions |
| first cannons building, `cannon_maker` | `cannon_maker_advance` | 2, Renaissance |
| flemish cloth right | `flemish_cloth_making` | 1, Traditions |

**So «a weaponry right granted where cannons cannot be built» cannot happen in
play**: by the age the rights exist at all, both buildings have been available for
an age or more. His words, and the files agree: «невозможно, чтобы произошёл
сценарий, когда ты выдал права на оружие городу, а в нём невозможно поставить
пушки или огнестрел».

**But the plan could still produce it, and that was a fault of its own.** The
«сейчас» plan handed out rights without asking `town_rights_enable` while refusing
a cannon maker because the country had not taken *its* advance — two different
moments inside one answer: rights as though it were age 3, buildings as though it
were today.

**Decided 2026-09-03: the plan does not ask the advance, and the deciding was
done by a run rather than by an argument.** The gate was built first — the plan
asking `has_advance` unless `_plan_by_end` — and it made the answer worse in a
way no reasoning had predicted. Münster holds `flemish_cloth_making` and not
`town_rights_enable`, so the gate left it **one** grantable charter of thirteen,
and «every town gets one» then handed that charter to all forty-eight towns:
cloth stood in 48 locations of 192 and the plan produced 30 goods instead of 35.

**The rule above it was right and the reason generalises.** A building you cannot
build today is not an answer to «what do I build»; **a charter is not something
you build**. It is a property of a town saying which buildings belong in it,
every country receives the nine general ones at one fixed age, and a plan is a
target to build towards. So the plan uses `potential`, exactly as the window
does.

**And the question the gate was meant to answer is answered in the report
instead.** `WTP RIGHT` prints `unlocked=` beside `grantable=`, and `tools/diag.py`
names the charters the plan is counting on that cannot be granted yet — which
costs one flag rather than a quarter of the ground.

**One correction to his wording, not to his point.** «Первый уровень» is not free
by default: `hand_cannon_guild` needs an age-1 advance exactly as `weapon_guild`
does, and most production buildings carry one too. What his save shows is a
country that simply had not taken that particular age-1 advance.

## Flemish cloth against royal textile, which he asked to have computed

They are mutually exclusive by the game's own `allow`, so it is a real choice.

- `royal_textile_rights`: **cloth +20%, fine cloth +20%, dyes +20%.** Age 3.
- `flemish_cloth_industries_right`: **cloth guild +5 levels, fine cloth guild +5
  levels**, plus `local_trades_per_burgher +0.25` and merchant capacity +0.25,
  which are trade and not production. Age 1, Dutch culture.

`guild_max_level = 1 + development × 0.1 + population × 0.05 + 5 if city + 10 if
megalopolis`, so **five levels are worth `5 ÷ cap` in output** and the crossover
is exact: **+5 levels beats +20% while the guild's cap is under 25 levels.**

- a plain town, cap around 10: flemish is +50% against +20% — **flemish, by far**;
- a city, cap 20-25: they meet;
- a megalopolis, cap well over 25: **royal textile**, and it also carries dyes,
  which flemish does not touch at all.

And flemish is available two whole ages earlier. **The general answer is flemish
in a town, royal textile in a great city** — but the mod cannot pick between them
today, because it scores no level right at all.

