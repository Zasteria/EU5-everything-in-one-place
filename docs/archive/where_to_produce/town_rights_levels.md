# Town rights: the level half, and the owner's worry about it

Split out of
[`../investigations/town_rights.md`](town_rights.md) on
2026-09-03, at its budget. **Settled and superseded**: the owner ruled on
2026-09-02 that the mod must never score building levels at all — «Мы смотрим на
общие ячейки… высчитывать это полный абсурд» — so the design below is not what
was built. A right is scored by *which goods it favours* and never by the size or
the kind of the favour.

Kept because the arithmetic in it is what decides Flemish cloth against royal
textile, which the mod still holds as a preference
(`generate.PREFERRED_RIGHT`). `tools/kb.py` searches it.

---

**3. A level right is a different unit and must not be added to the others.**
`flemish_cloth_industries_right` grants no efficiency at all: +5 levels of cloth
guild and +5 of fine cloth. An output right multiplies what you would have built
anyway; a level right adds levels. One is a ratio, the other a quantity, and a
score that sums them is the village-above-the-guild error in a new suit.

Score a level right on its own terms: **added levels × the value of one level
there**, which is the number the mod already computes.

### The owner's worry, and where it lands

> *"в локации где лимит будет 3 и он получит бонус +5 очевидно будет выгодней,
> чем в локации где можно поставить 15 и он получит +5"*

In **absolute** terms it is the other way round or equal: five levels produce
five levels' worth in both, and what differs is the value of one level — the
RGO bonus, which the mod already ranks on. In **proportional** terms he is
right: +5 on a cap of 3 is +167% and on 15 is +33%.

Neither is the whole answer, because the term neither of us can see is
**whether the levels can be filled** — levels want pops to employ, and a cap-3
location is small precisely because its development and population are small.
The mod does not model employment and should not pretend to.

So: rank on the absolute gain, print the cap before and after beside it, and let
the proportion be read off the two numbers rather than ranked on. That is the
one place in this design where the mod hands the judgement back.

