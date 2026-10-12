# Reading `performance_degradation.log`

Moved out of `docs/pitfalls/localization.md` on 10-12 (budget); it was never about localization.

**`performance_degradation.log` has columns that identify a playset.** `GUI
widgets` at the first in-game sample, `Total number of Gfx units` and
`Total number of Trade wagons` are deterministic for a given bookmark and data
set — 37 768 / 449 / 843 for this playset at 1337_04_01, every single run. When a
run arrived that was supposed to be vanilla, those three columns said so without
anyone having to be asked: 36 977 / 448 / 713. Use them to confirm a run was
configured the way the report says it was.

**`performance_degradation.log` records the in-game date, which turns it into a
controlled experiment for free.** A row whose date equals the row before it was
taken while the game was paused. Splitting an hour that way said more than any
guess: paused and idle adds zero widgets, growth does not scale with game days
(103 days added 138 widgets, 125 days added 10 936), and it does not scale with
the unit count on the map. That ruled out map icons, unit markers and the tick
itself without asking the player to run anything.

**Three samples of a performance log cannot tell a leak from a warm-up.** The
first reading of `performance_degradation.log` had memory climbing 280 MB a
minute and concluded the game was heading for swap. An hour of the same log says
otherwise: the working set peaks at 14.7 GB and then falls under 7 GB. What
actually grows without limit is the GUI widget count and the frame time. Read the
whole run before naming a cause; the file is a few kilobytes and there is no
excuse.
