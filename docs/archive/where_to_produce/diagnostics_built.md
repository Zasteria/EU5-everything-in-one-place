# «Диагностика» — как её строили и что она ответила

Вынесено из [`../pitfalls/diagnosis.md`](../../pitfalls/diagnosis.md) 2026-09-05,
когда тот перерос бюджет. **Кнопка построена, прогнана и подтверждена**; здесь
то, как её строили, и что она ответила с первого нажатия. Правила, которые из
этого остались, — в `diagnosis.md`. `kb.py` ищет и здесь.

## «Диагностика»: one press, everything, as text

**Built 2026-09-02.** The owner asked for it in as many words — «сделай какой-то
нормальный инструмент в моде, который будет отслеживать всё что можно
отслеживать… чтобы я мог его тебе показать или скопировать от него какой-то лог —
и ты сразу всё понимал "ОТ" и "ДО"» — after four runs went on four theories and
none on a measurement.

**A log and not a window, and that was measured rather than assumed.** The first
try was four columns beside the goods list; they came back saying glass stopped
at the placement stage in towns and could not say *in how many* towns, because a
column has one cell and the ladder had eaten the count. A screenshot has the same
problem one layer up. **Text has no width**, so every counter prints uncompressed
and no reading is ambiguous twice.

**And at the scale of the thing measured.** The first funnel asked the owner to
tick one good; his answer settles it for anything built here later: «эта проблема
— в плане расчётов по земле, где раскидываются ВСЕ товары, а не выбирается
конкретный». A per-good instrument cannot diagnose an all-goods pass, and the
symptom *is* the interaction between goods.

**Where it is:** the «Диагностика» button, Mod Menu → «Расчёт», beside «Показать
план». **It costs the plan nothing**: every counter except the per-pass pair is
read back afterwards off what the plan parked on the locations, so the expensive
button stays exactly as expensive as it was. **It reads state and writes none**,
so it is safe at any moment — pressed before a plan it prints zeros throughout,
which is itself the answer to «did the pass run at all».

**What it prints**, between `WTP ==== BEGIN` and `WTP ==== END`:

| block | what is in it |
| --- | --- |
| `BUILD` | the generator's own constants — methods, goods, rights, rounds, bands, tiers, and the 32 passes in order |
| `SELFTEST` | four lines that prove the dump itself, below |
| `PICK` / `SET` / `PASS` | everything chosen, both caps, which question was asked, and the totals the header line shows |
| `G<n>` | **one line per good, town and village apart**: `m` methods, `a` unlocked, `w` a method won, `r` of those with room left, `g` the gate would still open, `p` placed, `o` the best ordering it ever had — plus `ng`, the quota, the placements and the RGOs |
| `EDIT` | **the last press of the editor, in three lines** — what was asked (presses, op, good, reached, done/fail/norefill), what the scan found (fitn, cands), and what the walk saw where it stood (hit, town, load, esg, esw, evicted, room, placed before and after, load after, both caps). The location's numbers are parked into globals inside the walk, because a `debug_log` cannot reach the item a walk is on |
| `ROOM` | how many towns and villages still had room when the plan stopped |
| `P<n>` | what each of the 32 allocation passes did: sweeps used out of the guard, and the running total after it |
| `RIGHT <k>` | how many towns each urban right was granted in, and what it grants |
| `L` | one line per location, best first, with what was put in it — a good to a line, folded back into one line by `tools/diag.py` |
| `R` | the single-good ranking's own rows, for the case where the plan is right and the table it is read against is not |

**Reading a `G` line: the first zero left to right is the stage**, and the number
before it is how many locations got that far — the thing a column could not
carry. Three readings have different owners:

- `w > 0`, `r = 0` — **the ground filled up**. Not a fault in itself.
- `w > 0`, `r > 0`, `g = 0` — the good, or its building, **is already in every
  place that still has room**. That is the one-per-type rule, and whether it is
  right is a design question.
- `g > 0`, `p = 0` — **the allocator never gave it a turn.** Ours, and the three
  suspects are named on the same line: `q` the quota, `ng` against the tier the
  pass admits, and `o` against the band — a good whose `o` never reaches 200 has
  only the last band, by which time the towns are taken.

**Both caps print what they left out**, so a cap is never silently the answer.

**How the text gets out of the game:** `mods.bat → «Забрать диагностику из игры»`, or
`python3 tools/diag.py`. It finds the game's `logs`, takes the last report,
strips the log prefixes, folds each location's goods back onto its own line and
copies the result to the clipboard. `--raw` keeps the log's own shape; `--all`
takes every report in the file rather than the last.

**It comes out with the fault it finds.** The whole of it is `bag_wtp_diag*`,
`bag_wtp_dv*`/`_dg*`, the `_f*` counters, the two `_pass*` counters in
`_plan_allocate`, and one button.

## And it worked: what one press answered

**2026-09-02, the first press.** Four theories over four runs had not named the
cause; one press of the finished instrument did, and the report is what settled
it rather than any reasoning in this file.

**The number that did it: a town-side method won on 3 of 17 town-side
locations** — for glass, and for cloth, tools, pottery, jewelry, beer, leather,
paper, weaponry and eleven more; while sand, masonry and fiber_crops won on all
17. Fourteen of those «towns» take RGO buildings and refuse manufacturing, because
they are villages the player ticked into towns and a guild is `town = yes`. **The
tick moves a location to the plan's side of the ledger; it cannot move its rank in
the game.** `SETTLED.md` has the row.

**Twenty goods at once is why it is settled and one good was not.** The funnel's
first shape asked about one good and could not have distinguished the market
condition from the rank: only a line for *every* good shows sixteen goods with no
market condition stopped in exactly the same fourteen places.

**And the dump found two faults in itself**, which is the third time this file
records the probe finding the fault in the probe: `[glass, masonry]` in a
`debug_log` string is data-function syntax, and `error_log` writes into
`debug.log` too, so every headline arrived twice. Both in `research/engine.md`.

## A reader that guesses a format loses the run it was built for

**Closed, and the whole episode is in**
[`../archive/diagnosis_reader.md`](diagnosis_reader.md): `tools/diag.py`
guessed at the report's shape, five presses were summed into one «коротко», and
the run it was built for was spent reading a summary of the wrong thing. The rule
it produced: **the reader and the writer are generated from one description, or
the reader is a second guess about the first.**

## The report is not for the player, so the tool has to read it

**2026-09-02, his second press.** «Проверить насколько всё идеально и выгодно
распределено я не могу из-за того что это сложно для меня как человека… Ты мог
бы сам посмотреть.» He is right, and it is not a complaint about the format: 47
counters and 127 location rows are a session's input, not a person's.

So `tools/diag.py` **draws the conclusion and prints it first** — how full the
ground came out, how many buildings earn anything where they stand, how the goods
divide, which right holds how many towns, which passes ran out of sweeps. A dozen
lines of Russian at the top of the same file, and the same dozen in the console.
The detail stays underneath for the session.

**And one guard about guards.** The rule that a reader must refuse to hand back
nothing was written the day before, and its first version counted lines: fewer
out than in meant something was lost. On the first real report the fold honestly
turned 427 lines into 178 — four of every five are a good on a location's own row
— and the guard threw the folded version away and shipped the raw one. **Count
what must survive, not how much came out**: every `WTP` line except the `WTP LG`
rows that folding is for.
