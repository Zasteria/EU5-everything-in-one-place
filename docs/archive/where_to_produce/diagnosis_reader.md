# `tools/diag.py` — the reader that guessed a format

Split out of [`../pitfalls/diagnosis.md`](../../pitfalls/diagnosis.md) on
2026-09-04, at its budget. Closed; kept because it cost a run.
`tools/kb.py` searches it.

**2026-09-02, the first press.** The mod's half worked on the first load — button,
callback, effect and `debug_log` all — and the owner got a file of **zero bytes**,
because `tools/diag.py` cut the game's log prefix with a regex written against a
*guessed* shape. Nothing matched, so no line came out starting with `WTP`, and the
fold dropped every line it did not recognise.

Three rules came out of it, and they are about any reader of anybody else's
output:

- **Cut at what you wrote, not at what they wrote.** `WTP` is in every line of
  ours and in nothing else, so `line.find("WTP ")` is an answer where a regex
  over the prefix is a prediction.
- **Never drop what you do not recognise.** An unknown line goes through with a
  mark on it. A reader that silently discards is indistinguishable from a mod
  that never ran — which is exactly the confusion the whole instrument exists to
  remove.
- **Refuse to hand back nothing.** If the fold keeps less than half of what the
  log held, the raw block is written instead and the tool says so. An empty file
  is worse than no file: it looks like an answer.

**And a press has to be visible where it was pressed.** He expected a window; the
report is too long to read on screen and is not for him. The button's own
description now prints what the last collect saw, the same way «Считать» prints
its three numbers — so the press is never indistinguishable from a dead button.

### Three more, found in the same reader on 2026-09-03

All three had been in every report the owner sent, and none of them logged
anything. They are the second half of the rules above, stated as failures.

**A prefix is not a key.** `line.startswith("WTP RQ ")` was meant for a town's
charter scores and also matched `WTP RQ legend`, the one line that explains the
numbers. The legend arrives after the last location, when no row is open, so the
fold threw it away in silence: it is in **none** of the three reports of
2026-09-03, and nobody noticed because a legend's absence looks like a legend that
was never written. Had it arrived one line earlier it would have overwritten the
last town's scores instead. `re.match(r"WTP RQ \d", line)` now, and the legend is
printed *before* the rows rather than under two hundred of them.

**A row took every name it had been handed, and the mod handed it two.**
`debug_log_scopes` writes one line naming the current scope; the location block
called it before its `L` line **and again** before its `RQ` line, so the log held
each location's name twice and the fold gave every row from the second onwards
the previous location's name as well as its own — «WTP L Район Липпштадт (980)
Район Зост (981) rank=2». The owner, looking for one town in it: «Понятия не имею
где конкретно искать строку Гослара.» The second call is gone; the reader takes
the *nearest* name and marks the rest rather than joining them.

**A number can be labelled with another number's name.** `ranked_provs` in the
`PASS` line printed `_found`, which is the single-good ranking's province count,
and read `0` on every plan ever dumped. Nothing about a zero says it is the wrong
variable. **A field that is always zero deserves the same suspicion as a
safeguard that always fires**: check what it is reading before believing what it
says.

**And the one number that is honest and still misleads.** `q` in the goods line
is read back after the plan, so it carries the layer the open ladder added — one
per sweep — on top of the quota. `PASS quota=2` beside `clay q=2 rgo=2` reads as
the RGO discount doing nothing, and is the discount working and the open ladder
adding one back. An hour went into re-deriving that from three reports before the
line was made to say it. **A report that is read against itself has to say which
of its numbers were taken when.**

### A fix that follows from consistency is still a guess

**2026-09-03, and it cost a quarter of a plan.** The «Сейчас» plan refused a
building whose advance the country had not taken and, in the same answer, handed
out charters from an age it had not reached. That is a genuine inconsistency, it
was named in an investigation, and closing it needed no measurement to justify —
which is exactly why it went in without one.

The run: Münster holds one of the thirteen charters' advances, so the gate left
it one grantable charter, and «every town gets one» gave that charter to all
forty-eight towns. Cloth in 48 locations of 192; goods produced down from 35 to
30. Reverted the same day.

**The rule this repository already had was «a cause you cannot name is not a
cause — measure it».** This is its other half: **an argument about the shape of
the code is not a measurement about the answer**. The gate was consistent,
defensible, passed every checker, and made the output worse — because the rule it
collided with («каждый город обязательно получит право») was written when nine
charters were available and degenerates at one.

**What it does not mean is «change nothing without a run».** The same session
also removed dead work, corrected a scope misreading and rebuilt the pass order,
and all of those held. The distinction is what the change is *for*: repairing
something measured, versus tidying something that merely reads wrong. The second
kind is where a run is owed **before** the change ships, or where the change
should be a report field instead — which is what the advance became.

### A measurement answers the ground it was taken on

**2026-09-03, and it cost the same fault being closed twice.** The plan's bands
were measured on Westphalia — 48 locations, a quota of 2 a good — and the reading
was unambiguous: every good got roughly its share, the bands barely mattered, and
the relative-band idea was written up as unnecessary with the numbers to prove it.
The same build on northern Germany, 416 locations, quota 29:

```
cannons   candidate locations 103   quota 160   placed 2
goods reaching 1000 somewhere:  30, averaging 42 buildings
goods that never do:             8, averaging 12
an even share would be          36
```

Nothing about the formula changed between the two. **The quota binds on a small
ground and binds nothing on a large one**, and which of the two mechanisms is
doing the allocating flips completely between them. A measurement taken where the
quota binds says nothing at all about ground where it does not.

**So: before closing a question with a number, say what the number is a
measurement *of*.** «The bands are not the problem» was true of Westphalia and
false of the realm. The habit that catches it is cheap — name the regime in the
same sentence as the finding, and the next reader can see whether their ground is
the same one.

**And a corollary about asking for runs.** The press that overturned this was
asked for in the previous session and arrived in the same file as the small one,
which is the only reason the error lasted hours instead of days. **Where a
quantity in the formula scales with the ground — a quota, a room count, a
candidate count — one press is not evidence and two of different sizes are.**

